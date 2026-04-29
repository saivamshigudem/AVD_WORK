import pandas as pd
import os
from typing import Dict, Any, List
from pathlib import Path
# Adjust import to verify it works in context of the package or standalone
try:
    from src.models import ParsedReport, CleanedTable
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.models import ParsedReport, CleanedTable


# Add local poppler to path if it exists
try:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    deps_dir = os.path.join(project_root, 'deps')
    if os.path.exists(deps_dir):
        for root, dirs, files in os.walk(deps_dir):
            if 'pdftoppm.exe' in files or 'pdftoppm' in files:
                if root not in os.environ['PATH']:
                    os.environ['PATH'] += os.pathsep + root
                break
except Exception:
    pass


import unicodedata

def clean_text_content(text: str) -> str:
    """
    Cleans text by normalizing unicode, removing null bytes, 
    and fixing common encoding artifacts (replacement chars).
    """
    if not text:
        return ""
        
    # Normalize unicode characters (NFKC handles compatibility composition)
    text = unicodedata.normalize('NFKC', text)
    
    # Replace common artifact characters
    # \ufffd is the 'replacement character' often seen as a black diamond question mark
    text = text.replace('\ufffd', ' ')
    
    # Replace non-breaking spaces
    text = text.replace('\xa0', ' ')
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    return text.strip()

def parse_esg_reports(pdf_path: str) -> Dict[str, Any]:
    """
    Parse a single ESG PDF and return extracted text and table DataFrames.

    Returns a dict: { 'text': str, 'tables': [DataFrame, ...] }
    """
    data = {"text": "", "tables": []}

    if not os.path.exists(pdf_path):
        return data



    try:
        print(f"   [Docling] Starting advanced parsing for: {os.path.basename(pdf_path)}")
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
        from docling.datamodel.base_models import InputFormat

        # Configure Pipeline for Table Accuracy
        pipeline_options = PdfPipelineOptions(do_table_structure=True)
        # We can enable OCR if needed, but it adds time. Defaulting to False for speed unless requested.
        pipeline_options.do_ocr = False 
        pipeline_options.table_structure_options.mode = TableFormerMode.FAST
        # Enable image extraction as requested
        pipeline_options.generate_picture_images = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # Convert the file
        # Docling handles internal memory, but for extremely large files, this line is the heavy lifter.
        res = converter.convert(pdf_path)
        doc = res.document

        # Only use Markdown Export for High Quality Text Structure
        md_text = doc.export_to_markdown()
        data["text"] = md_text
        
        # 2. Extract Tables
        # Docling tables are powerful.
        for tbl in doc.tables:
            try:
                # Export to Pandas
                df = tbl.export_to_dataframe()
                
                # Basic Cleaning
                df.dropna(how='all', inplace=True) # Drop empty rows
                df.dropna(axis=1, how='all', inplace=True) # Drop empty cols
                
                # Convert all to string to prevent serialization issues
                df = df.astype(str)
                
                if not df.empty and len(df) > 1:
                     data["tables"].append(df)
            except Exception as e:
                print(f"   [Docling] Table export failed: {e}")

        print(f"   [Docling] Success! Extracted {len(data['tables'])} tables.")

    except ImportError:
        print("   [Error] Docling not installed. Run `pip install docling`.")
    except Exception as e:
        print(f"   [Error] Docling parsing failed: {e}")
        print("   [Fallback] Returning empty data.")

    return data



def table_to_sentences(table_rows: List[Dict], filename: str) -> str:
    """
    Converts a table (list of row dicts) into a semantic paragraph.
    Example: 'In Apple_2024_Report, Row 1 indicates: Revenue was 100M, Cost was 50M...'
    """
    sentences = []
    # Identify report year from filename (e.g., Apple_2025_ESG -> 2025)
    import re
    year_match = re.search(r'\d{4}', filename)
    year = year_match.group(0) if year_match else "Unknown Year"
    company_match = filename.split('_')[0]
    
    for row in table_rows:
        row_parts = []
        for k, v in row.items():
            if str(v).strip() and str(k).strip():
                row_parts.append(f"{k} was {v}")
        if row_parts:
            sentences.append(f"In {company_match} ({year}) report: " + ", ".join(row_parts) + ".")
            
    return "\n".join(sentences)

def clean_and_structure_tables(parsed_reports: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert DataFrames into structured JSON-like lists and perform basic cleaning settings.
    Validates output using Pydantic parsers.
    NOW ADDS: 'semantic_tables' field which is a text representation of the table.
    """
    structured = {}
    for fname, content in parsed_reports.items():
        # Prepare lists
        cleaned_tables = []
        semantic_tables_text = [] # new list to hold text representations
        
        for df in content.get("tables", []):
            try:
                # Drop fully empty rows/columns
                df = df.dropna(axis=0, how='all')
                df = df.dropna(axis=1, how='all')

                # Reset columns to string labels
                df.columns = [str(c).strip() for c in df.columns]

                # Convert numeric-like columns
                for col in df.columns:
                    try:
                        # Keep as object/string often safer for LLM context, but numeric helps metadata
                        # Here we just clean common artifacts
                        df[col] = df[col].astype(str).str.replace(r'\n', ' ', regex=True).str.strip()
                    except Exception:
                        pass

                # Convert to list of dicts
                rows = df.to_dict(orient='records')
                # Filter out garbage rows (e.g. all empty strings)
                valid_rows = [r for r in rows if any(str(v).strip() for v in r.values())]
                
                if valid_rows:
                    cleaned_tables.append(CleanedTable(rows=valid_rows))
                    # Convert to semantic text
                    semantic_text = table_to_sentences(valid_rows, fname)
                    semantic_tables_text.append(semantic_text)
                    
            except Exception as e:
                print(f"Error cleaning table in {fname}: {e}")
                continue

        # Create validated object
        report_dict = ParsedReport(
            filename=fname,
            text=content.get("text", ""),
            tables=cleaned_tables,
            metadata={"source": "docling"}
        ).model_dump()
        
        # Inject our new semantic table text into the dictionary (even if not in Pydantic model yet)
        report_dict["semantic_tables"] = semantic_tables_text
        
        structured[fname] = report_dict

    return structured


if __name__ == "__main__":
    reports_dir = "esg_reports"
    parsed_all = {}
    if os.path.exists(reports_dir):
        for f in os.listdir(reports_dir):
            if f.lower().endswith('.pdf'):
                parsed_all[f] = parse_esg_reports(os.path.join(reports_dir, f))

    structured = clean_and_structure_tables(parsed_all)
    # Simple verification print
    for fname, data in structured.items():
        print(f"File: {fname}, Text Length: {len(data['text'])}, Tables: {len(data['tables'])}")

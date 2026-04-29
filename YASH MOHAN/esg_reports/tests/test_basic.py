import os
import sys
import pytest

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.parsers.parse_esg_reports import parse_esg_reports, clean_and_structure_tables
from src.embeddings.chroma_store import chunk_text, table_to_markdown

def test_chunk_text():
    text = "A" * 2000 + "\n\n" + "B" * 1000
    chunks = chunk_text(text, chunk_size=1500)
    assert len(chunks) >= 2
    assert "A" in chunks[0]
    assert "B" in chunks[1]

def test_table_to_markdown():
    rows = [{"Col1": "Val1", "Col2": "Val2"}, {"Col1": "Val3", "Col2": "Val4"}]
    md = table_to_markdown(rows)
    assert "| Col1 | Col2 |" in md
    assert "| Val1 | Val2 |" in md

def test_parser_structure():
    # Mocking parser output for cleaning
    raw_data = {
        "report1.pdf": {
            "text": "some text",
            "tables": [] # mock empty first
        }
    }
    structured = clean_and_structure_tables(raw_data)
    assert "report1.pdf" in structured
    assert structured["report1.pdf"]["text"] == "some text"

from typing import Dict, Any, List
import re

def extract_key_metrics_from_structured(structured: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """
    Heuristic extractor that scans structured report content (text + tables)
    and returns simple numeric metrics per company.
    FASTER & MORE RELIABLE than Local LLM for batch processing.
    """
    metrics = {}

    # Specific patterns for each metric type
    # We use tuples: (Pattern List, IsPercentage)
    # IsPercentage=False means we explicitly IGNORE numbers followed by %
    metric_config = {
        'carbon_emissions': {
            'patterns': ['gross emissions', 'total carbon footprint', 'scope 1', 'scope 2', 'scope 3', 'total emissions', 'carbon\s+removal', 'emissions\s+by\s+sector'],
            'units': ['mt', 'million metric tons', 'tco2e', 'metric tons', 'mtco2e'],
            'is_percent': False
        },
        'energy_usage': {
            'patterns': ['purchased electricity', 'total energy', 'energy consumption', 'renewable energy', 'contracted renewable', 'electricity\s+consumption'],
            'units': ['gwh', 'mwh', 'gigawatt', 'gw'],
            'is_percent': False
        },
        'water_usage': {
            'patterns': ['water withdrawal', 'water consumption', 'freshwater', 'water replenishment', 'water access', 'water\s+use'],
            'units': ['gallons', 'cubic meters', 'million gallons', 'm3'],
            'is_percent': False
        },
        'waste_generated': {
            'patterns': ['waste generated', 'total waste', 'hazardous waste', 'waste diverted', 'diverted\s+.*waste', 'waste\s+from\s+operations', 'diverted', 'construction\s+waste'],
            'units': ['tons', 'metric tons', 'mt'],
            'is_percent': False
        },
        'renewable_energy_percent': {
            'patterns': ['renewable energy', 'renewable electricity', 'clean energy', 'carbon free energy'],
            'units': ['%'],
            'is_percent': True
        }
    }

    def parse_value_with_context(text_segment: str) -> float:
        """
        Parse a number from a small segment of text, handling units (k, m, b).
        Returns None if it looks like a year or unwanted percentage.
        """
        # Clean string
        txt = text_segment.lower().replace(',', '').replace('%', '')
        
        # Iterate through ALL numbers found in the segment
        # This handles cases like "Women in leadership 2025 goal: 45%"
        # where "2025" is found first but rejected as a year.
        for match in re.finditer(r'(-?\d+\.?\d*)', txt):
            val_str = match.group(1)
            try:
                val = float(val_str)
            except:
                continue
                
            # Immediate Year Check
            if 1990 <= val <= 2035 and val.is_integer():
                continue

            # Multiplier check (simplistic: looks at whole string, potentially unsafe if multiple numbers)
            # A better approach would be to look at text AROUND this specific match, but we'll stick to segment-level for now
            # as usually the segment is short (~100 chars).
            multiplier = 1.0
            if 'billion' in txt or ' b ' in txt: multiplier = 1_000_000_000.0
            elif 'million' in txt or ' m ' in txt or 'mmt' in txt: multiplier = 1_000_000.0
            elif 'thousand' in txt or ' k ' in txt: multiplier = 1_000.0
                
            final_val = val * multiplier
            
            # Sanity Checks
            if 1990 <= final_val <= 2035 and multiplier == 1.0: continue
            if final_val <= 3 and multiplier == 1.0 and 'scope' in txt: continue
            if final_val > 100_000_000_000: continue
            
            # If we passed all checks, this is our number
            return final_val
            
        return None

    def safe_text_extract(text: str, config: dict) -> float:
        """
        Scan text for patterns defined in config.
        """
        patterns = config['patterns']
        is_percent = config['is_percent']
        
        best_val = None
        
        for p in patterns:
            # We search for the pattern, then grab the next ~100 chars to look for a value
            # e.g. "Gross emissions: 15.4 million metric tons"
            # ALLOW matching across newlines by not including \n in the negated class
            regex = re.compile(rf"({p})[^0-9]{{0,100}}?(-?[\d,]+\.?\d*)", re.IGNORECASE | re.DOTALL)
            
            matches = regex.finditer(text)
            for m in matches:
                full_match = text[m.start():m.end()+100] # grab a bit more context for units (100 chars)
                
                # If we are strictly NOT a percentage, but see a %, skip
                if not is_percent and '%' in full_match:
                    continue
                
                parsed = parse_value_with_context(full_match)
                if parsed is not None:
                    # Specific percentage validation
                    if is_percent:
                        # 1. Must have '%' or 'percent' in the text
                        if '%' not in full_match and 'percent' not in full_match.lower():
                            continue
                        # 2. Value must be reasonable (<= 100)
                        if parsed > 100:
                            continue

                    # heuristic: keep the largest value found (usually "Total" > "Scope 1")
                    # BUT for percentages, we might want the largest distinct one? 
                    # Actually, usually "100%" is the goal/stat.
                    if best_val is None or parsed > best_val:
                        best_val = parsed
                        
        return best_val

    for fname, content in structured.items():
        print(f"[Metrics] Scanning {fname} using Heuristic Regex...")
        company_metrics = {}
        report_text = content.get('text', '')
        
        # 1. Text Extraction (Primary)
        # We process each category
        for cat, config in metric_config.items():
            val = safe_text_extract(report_text, config)
            if val is not None:
                company_metrics[cat] = val
        
        # 2. Table Fallback (Secondary, if Text didn't find anything)
        # (Simplified table scan for missing items)
        tables = content.get('tables', [])
        for table in tables:
            rows = table.get('rows', []) if isinstance(table, dict) else table
            for row in rows:
                for k, v in row.items():
                    if not k: continue
                    k_lower = str(k).lower()
                    
                    for cat, config in metric_config.items():
                        if cat in company_metrics: continue # Already found in text
                        
                        # Check if column header matches a pattern using Regex
                        # Use re.search because patterns can be regex strings
                        for pat in config['patterns']:
                             if re.search(pat, k_lower, re.IGNORECASE):
                                 # Attempt to parse v
                                 try:
                                     # rudimentary clean
                                     v_str = str(v)
                                     
                                     # For table cells, percentages might simpler "50%" or just "50"
                                     # if the column header had "%". 
                                     # For now adhering to strict: if not is_percent, discard %
                                     if not config['is_percent'] and '%' in v_str: continue

                                     parsed_v = parse_value_with_context(v_str)

                                     # Additional heuristic for Tables:
                                     # If the header has 'million', we multiply
                                     if 'million' in k_lower or 'mm' in k_lower:
                                         if parsed_v and parsed_v < 100000: # avoid double multiplying
                                             parsed_v *= 1_000_000

                                     if parsed_v:
                                         company_metrics[cat] = parsed_v
                                         break # Found this cat for this row
                                 except: pass

        metrics[fname] = company_metrics

    return metrics

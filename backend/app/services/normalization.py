import re
from typing import Optional

import unicodedata

def normalize_team_name(name: Optional[str]) -> str:
    """
    Normalize provider-specific team names to a shared comparison key.
    Includes comprehensive aliases for all supported leagues.
    """
    if not name:
        return ""
        
    # 1. Normalize characters (handle accents like Atlético -> Atletico)
    v = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    v = v.encode('ascii', 'ignore').decode('ascii').lower().strip()
    
    # 2. Clean special characters and whitespace
    v = re.sub(r"[^a-z0-9 ]", "", v)
    v = re.sub(r"\s+", " ", v).strip()
    
    # 2. First-pass Alias check (with suffixes like 'united')
    compact_raw = v.replace(" ", "")
    
    # Comprehensive Alias Map
    alias = {
        # Eredivisie
        "fcutrecht": "utrecht", "heraclesalmelo": "heracles", "ajaxamsterdam": "ajax",
        "psveindhoven": "psv", "azalkmaar": "az", "fctwente": "twente",
        # La Liga
        "celta": "celtavigo", "celtavigo": "celtavigo", "celtadevigo": "celtavigo",
        "realbetis": "betis", "realbetisbalompie": "betis",
        "athleticclub": "athleticbilbao", "athletic": "athleticbilbao",
        "atleticodemadrid": "atleticomadrid", "atletico": "atleticomadrid", "atlmadrid": "atleticomadrid", "atleti": "atleticomadrid",
        "deportivoalaves": "alaves", "alaves": "alaves", "espanyolbarcelona": "espanyol",
        "rayovallecano": "rayo", "realvalladolid": "valladolid", "realsociedad": "realsociedad",
        # Premier League
        "manchesterunited": "manutd", "manunited": "manutd", "manutd": "manutd",
        "manchestercity": "mancity", "mancity": "mancity",
        "tottenhamhotspur": "tottenham", "wolverhamptonwanderers": "wolverhampton", "wolves": "wolverhampton",
        "newcastleunited": "newcastle", "nottinghamforest": "nottmforest",
        "brightonandhovealbion": "brighton", "leicestercity": "leicester",
        "westhamunited": "westham", "ipswichtown": "ipswich",
        # Serie A
        "acmilan": "milan", "milan": "milan", "internazionale": "inter", "inter": "inter",
        "hellas": "hellasverona", "hellasveronafc": "hellasverona", "verona": "hellasverona",
        # Bundesliga
        "bayernmunich": "bayernmunchen", "bayern": "bayernmunchen", "fcbayern": "bayernmunchen",
        "bayerleverkusen": "leverkusen", "borussiamgladbach": "mgladbach", "borussiadortmund": "dortmund",
        "eintrachtfrankfurt": "frankfurt",
        # Ligue 1
        "parissaintgermain": "psg", "psg": "psg", "olympiquemarseille": "marseille",
        "olympiquelyonnais": "lyon", "asstienne": "stetienne", "saintetienne": "stetienne",
    }
    
    if compact_raw in alias:
        return alias[compact_raw]
        
    # 3. Second-pass (Refined): Remove only common football noise (FC, CF, etc.)
    # We avoid stripping 'united', 'real', 'atletico' to prevent collisions (e.g., Real Madrid vs Atletico Madrid)
    v_refined = re.sub(r"\b(fc|cf|ac|afc|sc|sv|fk|ifk|club|de|the|as|calcio)\b", "", v)
    v_refined = re.sub(r"\s+", " ", v_refined).strip()
    compact_refined = v_refined.replace(" ", "")
    
    if compact_refined in alias:
        return alias[compact_refined]
        
    return compact_refined or compact_raw

#!/usr/bin/env python3
"""
Script d'introspection des specs OpenAPI France Travail
Extrait les schémas de données pour préparer le pipeline
"""
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("/Users/akimguentas/Documents/elevia-compass")

def extract_schema_from_openapi(spec_path):
    """Extrait les schémas de réponse d'une spec OpenAPI"""
    with open(spec_path, 'r', encoding='utf-8') as f:
        spec = json.load(f)

    schemas = {}

    # Extraire les schémas des composants
    if 'components' in spec and 'schemas' in spec['components']:
        for name, schema in spec['components']['schemas'].items():
            schemas[name] = {
                'type': schema.get('type'),
                'properties': list(schema.get('properties', {}).keys()),
                'required': schema.get('required', [])
            }

    # Extraire les endpoints principaux
    endpoints = []
    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.upper() in ['GET', 'POST']:
                endpoints.append({
                    'path': path,
                    'method': method.upper(),
                    'summary': details.get('summary', ''),
                    'parameters': [p.get('name') for p in details.get('parameters', [])]
                })

    return {
        'title': spec.get('info', {}).get('title'),
        'version': spec.get('openapi'),
        'endpoints': endpoints,
        'schemas': schemas
    }

def main():
    print("="*80)
    print("🔍 INSPECTION DES SPECS OPENAPI FRANCE TRAVAIL")
    print("="*80)

    specs_files = [
        ("Offres d'emploi.json", "OFFRES"),
        ("ROME 4.0 - Compétences.json", "COMPETENCES"),
        ("Marché du travail.json", "MARCHE"),
        ("ROME V4.0 - Situations de travail.json", "SITUATIONS")
    ]

    all_specs = {}

    for filename, key in specs_files:
        path = DATA_DIR / filename
        if path.exists():
            print(f"\n📄 {filename}")
            print("-"*80)

            spec_info = extract_schema_from_openapi(path)
            all_specs[key] = spec_info

            print(f"Title: {spec_info['title']}")
            print(f"Version: {spec_info['version']}")
            print(f"\nEndpoints principaux ({len(spec_info['endpoints'])}):")

            for ep in spec_info['endpoints'][:5]:
                print(f"  [{ep['method']}] {ep['path']}")
                if ep['summary']:
                    print(f"      {ep['summary']}")

            print(f"\nSchémas disponibles ({len(spec_info['schemas'])}):")
            for name, schema in list(spec_info['schemas'].items())[:5]:
                print(f"  - {name} ({schema['type']})")
                if schema['properties']:
                    props = ', '.join(schema['properties'][:5])
                    print(f"    Props: {props}...")

    # Sauvegarder l'introspection
    output_path = DATA_DIR / 'data' / 'openapi_inspection.json'
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_specs, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print(f"✅ Introspection sauvegardée: {output_path}")
    print("="*80)

    # Résumé pour le pipeline
    print("\n📊 RÉSUMÉ POUR LE PIPELINE:")
    print("-"*80)

    if 'OFFRES' in all_specs:
        offres_schemas = all_specs['OFFRES']['schemas']
        if offres_schemas:
            print(f"✅ Offres d'emploi: {len(offres_schemas)} schémas détectés")

    if 'COMPETENCES' in all_specs:
        comp_schemas = all_specs['COMPETENCES']['schemas']
        if comp_schemas:
            print(f"✅ ROME Compétences: {len(comp_schemas)} schémas détectés")

    if 'MARCHE' in all_specs:
        marche_schemas = all_specs['MARCHE']['schemas']
        if marche_schemas:
            print(f"✅ Marché du travail: {len(marche_schemas)} schémas détectés")

    if 'SITUATIONS' in all_specs:
        sit_schemas = all_specs['SITUATIONS']['schemas']
        if sit_schemas:
            print(f"✅ Situations de travail: {len(sit_schemas)} schémas détectés")

if __name__ == '__main__':
    main()

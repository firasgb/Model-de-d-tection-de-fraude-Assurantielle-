#!/usr/bin/env python3
"""
Test script pour vrifier l'API de gestion des versions du modle
"""
import requests
import time
import json

API_URL = "http://localhost:8000"

def test_versions_api():
    """Test des endpoints de l'API versions"""
    print(" Test de l'API de gestion des versions...")

    try:
        # Test GET /model/versions
        print("\n Rcupration de toutes les versions...")
        response = requests.get(f"{API_URL}/model/versions")
        if response.status_code == 200:
            data = response.json()
            print(f" {len(data.get('versions', []))} versions trouves")
            print(f" Version active: {data.get('active_version', 'Aucune')}")

            if data.get('versions'):
                # Afficher les dtails de la premire version
                v = data['versions'][0]
                print(f"   Version {v['version']}: {v['notes']}")
                print(f"      Cre le: {v['created_at']}")
                print(f"      Active: {v['active']}")
        else:
            print(f" Erreur GET /model/versions: {response.status_code}")

        # Test GET /model/versions/{version_num} pour la version 1
        if data.get('versions'):
            version_num = data['versions'][0]['version']
            print(f"\n Dtails de la version {version_num}...")
            response = requests.get(f"{API_URL}/model/versions/{version_num}")
            if response.status_code == 200:
                v_detail = response.json()
                print(" Dtails rcuprs avec succs")
                print(f"   F1-Score: {v_detail.get('f1_score', 'N/A')}")
                print(f"   Precision: {v_detail.get('precision', 'N/A')}")
            else:
                print(f" Erreur GET /model/versions/{version_num}: {response.status_code}")

        # Test POST /model/versions/{version_num}/activate pour activer une version
        if data.get('versions') and len(data['versions']) > 1:
            version_to_activate = data['versions'][1]['version']
            print(f"\n Activation de la version {version_to_activate}...")
            response = requests.post(f"{API_URL}/model/versions/{version_to_activate}/activate")
            if response.status_code == 200:
                print(" Version active avec succs")
                # Vrifier que la version active a chang
                response = requests.get(f"{API_URL}/model/versions")
                if response.status_code == 200:
                    new_data = response.json()
                    print(f" Nouvelle version active: {new_data.get('active_version', 'Aucune')}")
            else:
                print(f" Erreur activation version {version_to_activate}: {response.status_code}")

        print("\n Tests de l'API termins!")

    except requests.exceptions.ConnectionError:
        print(" Impossible de se connecter au backend. Vrifiez qu'il est dmarr sur http://localhost:8000")
    except Exception as e:
        print(f" Erreur lors des tests: {e}")

if __name__ == "__main__":
    # Attendre que le backend soit prt
    print(" Attente du dmarrage du backend...")
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            if response.status_code == 200:
                print(" Backend prt!")
                test_versions_api()
                break
        except:
            print(f"   Tentative {attempt + 1}/{max_attempts}...")
            time.sleep(10)
    else:
        print(" Backend non accessible aprs 5 minutes d'attente")

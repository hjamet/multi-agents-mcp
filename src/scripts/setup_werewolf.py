import sys
import os
import uuid
import random

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.core.state import StateStore

def setup_werewolf_anonymized():
    store = StateStore()
    
    def update_logic(state):
        # 1. Clear State
        state["conversation_id"] = str(uuid.uuid4())
        state["messages"] = []
        state["turn"] = {"current": None, "next": None}
        
        # 2. Global Context
        state.setdefault("config", {})["context"] = (
            "Nous jouons au Loup-Garou de Thiercelieux. "
            "C'est la Nuit. Tous le monde dort. "
            "Le MJ (Maitre du Jeu) va orchestrer les tours. "
            "Les Loups doivent se mettre d'accord pour tuer un Villageois. "
            "La Voyante peut voir un rôle. La Sorcière peut tuer ou sauver. "
            "IMPORTANT: Les identités sont cachées derrière 'Habitant #N'."
        )
        
        profiles = []
        
        # --- PROFILES ---
        # Schema: 
        # name: Internal ID (for connections)
        # description: Internal Admin Note
        # display_name: Public Chat Name (Base)
        # public_description: Public Chat Description
        
        # MJ
        profiles.append({
            "name": "MaitreDuJeu",
            "description": "Admin du jeu",
            "display_name": "MaitreDuJeu",
            "public_description": "L'Orchestrateur",
            "system_prompt": "Tu es le Maitre du Jeu. Tu diriges la partie. Appelle les rôles : Voyante, puis Loups, puis Sorcière.",
            "capabilities": ["public", "private", "audience", "open"], 
            "connections": [],
            "count": 1
        })
        
        # Villageois
        profiles.append({
            "name": "Villageois",
            "description": "Simple Villageois",
            "display_name": "Habitant",
            "public_description": "Citoyen de Thiercelieux",
            "system_prompt": "Tu es un simple Villageois. Tu dors la nuit. Tu ne connais pas les autres rôles.",
            "capabilities": ["public", "audience"],
            "connections": [
                {"target": "MaitreDuJeu", "context": "Obéis au MJ."}
            ],
            "count": 5
        })
        
        # Loup-Garou
        profiles.append({
            "name": "LoupGarou",
            "description": "Les Tueurs",
            "display_name": "Habitant",
            "public_description": "Citoyen de Thiercelieux",
            "system_prompt": "Tu es un Loup-Garou. Tu chasses la nuit avec tes alliés.",
            "capabilities": ["public", "private", "audience"],
            "connections": [
                {"target": "MaitreDuJeu", "context": "Obéis au MJ."},
                {"target": "LoupGarou", "context": "Ton Allié Loup. Coopère."}
            ],
            "count": 2
        })

        # Voyante
        profiles.append({
            "name": "Voyante",
            "description": "Peut voir les rôles",
            "display_name": "Habitant",
            "public_description": "Citoyen de Thiercelieux",
            "system_prompt": "Tu es la Voyante. Chaque nuit, tu peux demander au MJ de révéler le rôle d'un joueur.",
            "capabilities": ["public", "private", "audience"],
            "connections": [
                {"target": "MaitreDuJeu", "context": "Demande au MJ de voir une carte."}
            ],
            "count": 1
        })

        # Sorcière
        profiles.append({
            "name": "Sorciere",
            "description": "A des potions",
            "display_name": "Habitant",
            "public_description": "Citoyen de Thiercelieux",
            "system_prompt": "Tu es la Sorcière. Tu as une potion de vie et de mort.",
            "capabilities": ["public", "private", "audience"],
            "connections": [
                {"target": "MaitreDuJeu", "context": "Indique au MJ si tu utilises tes potions."}
            ],
            "count": 1
        })
        
        state["config"]["profiles"] = profiles
        state["config"]["total_agents"] = 10 
        
        # --- GENERATE INSTANCES ---
        # 1. Flatten list of needed agents
        # List of dicts: { "profile": p, "role": prompt }
        pending_slots = []
        
        for p in profiles:
            count = p.get("count", 0)
            for _ in range(count):
                pending_slots.append({
                    "profile_ref": p["name"],
                    "role": p["system_prompt"],
                    "display_base": p.get("display_name", p["name"]),
                    "public_desc": p.get("public_description", "")
                })
        
        # 2. Shuffle to randomize IDs
        # (MJ is usually unique/fixed name, but strict shuffle is fairer if multiple MJs existed. 
        # Here MJ has display_name="MaitreDuJeu" so he will be distinct from "Habitant")
        random.shuffle(pending_slots)
        
        # 3. Assign IDs using Global Counters per Display Base
        counters = {} # "Habitant" -> 1, "MaitreDuJeu" -> 1
        new_agents = {}
        
        for slot in pending_slots:
            base = slot["display_base"]
            counters.setdefault(base, 0)
            counters[base] += 1
            
            # ID Generation
            # If total of this base > 1 -> Add #Number
            # But here we want strict anonymity. "Habitant #1" is standard.
            # Even if only 1, "Habitant #1" is fine, or "Habitant". 
            # Let's count totals first? 
            # Logic: If duplicate bases exist, use suffix.
            
            # Simple approach: Always append #N if base is "Habitant".
            # For "MaitreDuJeu" (count=1), maybe just "MaitreDuJeu".
            
            # Let's pre-count totals
            total_for_base = sum(1 for s in pending_slots if s["display_base"] == base)
            
            if total_for_base > 1:
                agent_id = f"{base} #{counters[base]}"
            else:
                agent_id = base
                
            new_agents[agent_id] = {
                "role": slot["role"],
                "status": "pending_connection",
                "profile_ref": slot["profile_ref"]
            }
            
        state["agents"] = new_agents
        
        return "Werewolf Anonymized Setup Complete (10 roles, shuffled IDs)"

    msg = store.update(update_logic)
    print(msg)

if __name__ == "__main__":
    setup_werewolf_anonymized()


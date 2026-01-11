import sys
import os
import uuid
import random

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.core.state import StateStore

def setup_werewolf_v2():
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
            "La Voyante peut voir un rôle. La Sorcière peut tuer ou sauver."
        )
        
        profiles = []
        
        # --- PROFILES ---
        # Note: Description is PUBLIC. System Prompt is PRIVATE (Role).
        
        # MJ
        profiles.append({
            "name": "MaitreDuJeu",
            "description": "L'Orchestrateur (MJ)",
            "system_prompt": "Tu es le Maitre du Jeu. Tu diriges la partie. Appelle les rôles : Voyante, puis Loups, puis Sorcière.",
            "capabilities": ["public", "private", "audience", "open"], 
            "connections": [],
            "count": 1
        })
        
        # Villageois (Simple)
        profiles.append({
            "name": "Villageois",
            "description": "Habitant de Thiercelieux",
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
            "description": "Habitant de Thiercelieux", # Deceptive Description
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
            "description": "Habitant de Thiercelieux", # Deceptive
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
            "description": "Habitant de Thiercelieux", # Deceptive
            "system_prompt": "Tu es la Sorcière. Tu as une potion de vie et de mort.",
            "capabilities": ["public", "private", "audience"],
            "connections": [
                {"target": "MaitreDuJeu", "context": "Indique au MJ si tu utilises tes potions."}
            ],
            "count": 1
        })
        
        state["config"]["profiles"] = profiles
        state["config"]["total_agents"] = 10 # 1MJ + 5Vill + 2Loups + 1Voy + 1Sorc = 10
        
        # --- INSTANCES ---
        # Pool names
        names_pool = ["Marc", "Sophie", "Antoine", "Julie", "Pierre", "Marie", "Luc", "Thomas", "Emma"]
        random.shuffle(names_pool)
        
        new_agents = {}
        
        # 1. MJ
        new_agents["MaitreDuJeu"] = {
            "role": profiles[0]["system_prompt"],
            "status": "pending_connection",
            "profile_ref": "MaitreDuJeu"
        }
        
        # 2. Assign Special Roles
        # Voyante
        name_v = names_pool.pop()
        new_agents[name_v] = {"role": profiles[3]["system_prompt"], "status": "pending_connection", "profile_ref": "Voyante"}
        
        # Sorcière
        name_s = names_pool.pop()
        new_agents[name_s] = {"role": profiles[4]["system_prompt"], "status": "pending_connection", "profile_ref": "Sorciere"}
        
        # 3. Wolves (2)
        for _ in range(2):
            name = names_pool.pop()
            new_agents[name] = {"role": profiles[2]["system_prompt"], "status": "pending_connection", "profile_ref": "LoupGarou"}
            
        # 4. Villagers (5)
        for _ in range(5):
            name = names_pool.pop()
            new_agents[name] = {"role": profiles[1]["system_prompt"], "status": "pending_connection", "profile_ref": "Villageois"}
            
        state["agents"] = new_agents
        
        return "Werewolf V2 Setup Complete (10 roles)"

    msg = store.update(update_logic)
    print(msg)

if __name__ == "__main__":
    setup_werewolf_v2()

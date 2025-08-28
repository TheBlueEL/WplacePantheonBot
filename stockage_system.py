import discord
from discord.ext import commands
from discord import app_commands
import json
import re
from difflib import SequenceMatcher
from datetime import datetime
import asyncio
import os

class StockageSystem:
    def __init__(self):
        self.api_data = {}
        self.item_request_data = {}
        self.load_data()

    def load_data(self):
        """Charge les données depuis les fichiers JSON"""
        try:
            with open('API_JBChangeLogs.json', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    self.api_data = json.loads(content)
                else:
                    self.api_data = {}
        except (FileNotFoundError, json.JSONDecodeError):
            self.api_data = {}

        try:
            with open('item_request.json', 'r', encoding='utf-8') as f:
                self.item_request_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.item_request_data = {}

    def load_stockage_data(self):
        """Charge les données de stockage"""
        try:
            with open('stockage_data.json', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
                else:
                    return {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_stockage_data(self, data):
        """Sauvegarde les données de stockage"""
        try:
            with open('stockage_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du stockage: {e}")
            return False

    def update_stockage_values(self):
        """Met à jour les valeurs du stockage depuis l'API"""
        stockage_data = self.load_stockage_data()

        for stock_key, stock_data in stockage_data.items():
            # Extraire le nom original de l'item (sans statut)
            base_name = re.sub(r'\s*\([^)]*\)$', '', stock_key)

            # Chercher dans l'API
            for api_name, api_data in self.api_data.items():
                if api_name == base_name or re.sub(r'\s*\([^)]*\)', '', api_name) == base_name:
                    # Mettre à jour toutes les données sauf la quantité
                    for key, value in api_data.items():
                        if key != 'quantity':
                            stock_data[key] = value
                    break

        self.save_stockage_data(stockage_data)

    def add_item_to_stock(self, item_name, item_data, status, quantity=1):
        """Ajoute un item au stock"""
        stockage_data = self.load_stockage_data()

        # Créer une clé unique basée sur le nom et le statut
        stock_key = f"{item_name} ({status})" if status != "Clean" else item_name

        if stock_key in stockage_data:
            # Augmenter la quantité si l'item existe déjà
            stockage_data[stock_key]['quantity'] += quantity
        else:
            # Créer un nouvel entry
            new_item = item_data.copy()
            new_item['quantity'] = quantity
            new_item['status'] = status
            stockage_data[stock_key] = new_item

        self.save_stockage_data(stockage_data)
        return True

    def extract_separators(self, text):
        """Extrait les items en utilisant les séparateurs +, ,, and"""
        # Pattern pour détecter les séparateurs avec espaces
        separators = [
            r'\s+\+\s+', r'\s+\+', r'\+\s+',  # variations de +
            r'\s+,\s+', r'\s+,', r',\s+',     # variations de ,
            r'\s+and\s+', r'\s+and', r'and\s+' # variations de and
        ]

        # Remplacer tous les séparateurs par |
        for sep in separators:
            text = re.sub(sep, '|', text, flags=re.IGNORECASE)

        # Diviser par |
        items = [item.strip() for item in text.split('|') if item.strip()]
        return items

    def extract_quantity(self, item_text):
        """Extrait la quantité de l'item"""
        # Chercher des patterns comme "x2", "2x", "quantity 3", etc.
        quantity_patterns = [
            r'x(\d+)',
            r'(\d+)x',
            r'quantity\s*(\d+)',
            r'qty\s*(\d+)',
            r'q\s*(\d+)'
        ]

        quantity = 1
        for pattern in quantity_patterns:
            match = re.search(pattern, item_text, re.IGNORECASE)
            if match:
                quantity = int(match.group(1))
                item_text = re.sub(pattern, '', item_text, flags=re.IGNORECASE)
                break

        return quantity, item_text.strip()

    def extract_type(self, item_text):
        """Extrait le type de l'item avec priorité aux noms complets"""
        item_text_lower = item_text.lower()

        # Vérifier d'abord les hyperchromes
        if re.search(r'\bhyper\b', item_text_lower):
            # Supprimer "hyper" du texte
            item_text = re.sub(r'\bhyper\b', '', item_text, flags=re.IGNORECASE).strip()
            return "Hyperchrome", item_text

        # Vérifier les types normaux avec priorité aux noms les plus longs
        types_data = self.item_request_data.get('type', {})

        best_match = None
        best_score = 0
        matched_alias = ""

        for official_type, aliases in types_data.items():
            for alias in aliases:
                # Créer un pattern pour détecter l'alias avec des espaces flexibles
                alias_pattern = re.escape(alias.lower()).replace(r'\ ', r'\s+')
                pattern = r'\b' + alias_pattern + r'\b'
                match = re.search(pattern, item_text_lower)

                if match:
                    # Priorité aux matches plus longs et plus précis
                    score = len(alias) * 10
                    # Bonus si c'est une correspondance exacte
                    if alias.lower() == match.group().lower():
                        score += 5

                    if score > best_score:
                        best_match = official_type
                        best_score = score
                        matched_alias = alias

        if best_match:
            # Supprimer le type trouvé du texte
            alias_pattern = re.escape(matched_alias.lower()).replace(r'\ ', r'\s+')
            pattern = r'\b' + alias_pattern + r'\b'
            item_text = re.sub(pattern, '', item_text, flags=re.IGNORECASE).strip()
            return best_match, item_text

        return "None", item_text

    def extract_status(self, item_text):
        """Extrait le statut (Clean/Dupe) de l'item"""
        item_text_lower = item_text.lower()

        # Statuts Clean avec espaces
        clean_patterns = [r'\s+clean\s+', r'\s+clean\b', r'\bclean\s+', r'\s+c\s+', r'\s+c\b', r'\bc\s+']
        # Statuts Dupe avec espaces
        dupe_patterns = [
            r'\s+duped?\s+', r'\s+duped?\b', r'\bduped?\s+',
            r'\s+duplicat(or|ed)\s+', r'\s+duplicat(or|ed)\b', r'\bduplicat(or|ed)\s+',
            r'\s+d\s+', r'\s+d\b', r'\bd\s+'
        ]

        status = "Clean"  # Par défaut

        for pattern in dupe_patterns:
            if re.search(pattern, item_text_lower):
                status = "Dupe"
                item_text = re.sub(pattern, ' ', item_text, flags=re.IGNORECASE)
                break

        if status == "Clean":
            for pattern in clean_patterns:
                if re.search(pattern, item_text_lower):
                    item_text = re.sub(pattern, ' ', item_text, flags=re.IGNORECASE)
                    break

        return status, item_text.strip()

    def extract_year(self, item_text):
        """Extrait l'année pour les hyperchromes"""
        years_data = self.item_request_data.get('years_list', {})
        aliases = years_data.get('aliases', {})
        years = years_data.get('years', {})

        # Chercher dans les aliases d'abord
        for alias, year in aliases.items():
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, item_text):
                item_text = re.sub(pattern, '', item_text, flags=re.IGNORECASE)
                return year, item_text.strip()

        # Chercher dans les années complètes
        for year in years.keys():
            pattern = r'\b' + re.escape(year) + r'\b'
            if re.search(pattern, item_text):
                item_text = re.sub(pattern, '', item_text, flags=re.IGNORECASE)
                return year, item_text.strip()

        return None, item_text

    def get_hyperchrome_default_status(self, year):
        """Détermine le statut par défaut pour un hyperchrome selon l'année"""
        if not year:
            return "Clean"

        no_duped_years = self.item_request_data.get('no_duped_years', [])

        if year in no_duped_years:
            return "Clean"
        else:
            return "Dupe"

    def character_similarity(self, text1, text2):
        """Calcule la similarité de caractères entre deux textes"""
        text1_chars = set(text1.lower())
        text2_chars = set(text2.lower())

        if not text1_chars or not text2_chars:
            return 0

        intersection = text1_chars.intersection(text2_chars)
        union = text1_chars.union(text2_chars)

        return len(intersection) / len(union) if union else 0

    def pattern_similarity(self, text1, text2, n=2):
        """Calcule la similarité basée sur les patterns de n caractères"""
        def get_patterns(text, n):
            text = text.lower()
            return [text[i:i+n] for i in range(len(text)-n+1)]

        patterns1 = get_patterns(text1, n)
        patterns2 = get_patterns(text2, n)

        if not patterns1 or not patterns2:
            return 0

        # Calculer les patterns communs avec leur position
        common_patterns = 0
        consecutive_bonus = 0

        for i, p1 in enumerate(patterns1):
            for j, p2 in enumerate(patterns2):
                if p1 == p2:
                    common_patterns += 1
                    # Bonus pour les patterns consécutifs
                    if abs(i - j) <= 1:
                        consecutive_bonus += 0.5

        total_patterns = len(patterns1) + len(patterns2)
        if total_patterns == 0:
            return 0

        base_score = (common_patterns * 2) / total_patterns
        return min(1.0, base_score + (consecutive_bonus / total_patterns))

    def basic_similarity(self, text1, text2):
        """Calcule la similarité de base entre deux textes"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def find_best_match(self, search_text, item_type, year=None):
        """Trouve le meilleur match pour un item avec algorithme de scoring amélioré"""
        candidates = []

        # Collecter tous les candidats possibles
        for item_name, item_data in self.api_data.items():
            candidates.append((item_name, item_data, item_name))

        # Ajouter les hyperchromes spéciaux
        hyper_data = self.item_request_data.get('hyper', {})
        for official_name, aliases in hyper_data.items():
            for alias in aliases:
                # Simuler des données pour les hyperchromes
                fake_data = {"cash_value": "Unknown", "duped_value": "Unknown", "demand": "Unknown"}
                candidates.append((official_name, fake_data, alias))

        # Filtrer par type si spécifié
        if item_type == "Hyperchrome":
            if year:
                # Filtrer par année pour les hyperchromes
                filtered_candidates = []
                for item_name, item_data, display_name in candidates:
                    if year in item_name:
                        filtered_candidates.append((item_name, item_data, display_name))
                candidates = filtered_candidates if filtered_candidates else candidates
            else:
                # Garder seulement les hyperchromes
                filtered_candidates = []
                for item_name, item_data, display_name in candidates:
                    if "hyper" in item_name.lower() or "hyper" in display_name.lower():
                        filtered_candidates.append((item_name, item_data, display_name))
                    # Vérifier aussi dans les hyperchromes spéciaux
                    for hyper_name in hyper_data.keys():
                        if hyper_name == item_name:
                            filtered_candidates.append((item_name, item_data, display_name))
                            break
                candidates = filtered_candidates if filtered_candidates else candidates

        elif item_type != "None":
            # Filtrer par type spécifique
            filtered_candidates = []
            for item_name, item_data, display_name in candidates:
                if f"({item_type})" in item_name:
                    filtered_candidates.append((item_name, item_data, display_name))
            candidates = filtered_candidates if filtered_candidates else candidates

        if not candidates:
            return None, []

        # Nettoyer le nom de recherche (enlever les parenthèses de type)
        clean_search = re.sub(r'\([^)]*\)', '', search_text).strip()

        # Calculer les scores pour chaque candidat
        scored_candidates = []
        for item_name, item_data, display_name in candidates:
            clean_item_name = re.sub(r'\([^)]*\)', '', item_name).strip()
            clean_display_name = re.sub(r'\([^)]*\)', '', display_name).strip()

            # Utiliser le nom d'affichage pour la comparaison si disponible
            comparison_name = clean_display_name if clean_display_name != clean_item_name else clean_item_name

            # Filtrage par similarité de caractères (40% minimum)
            char_similarity = self.character_similarity(clean_search, comparison_name)
            if char_similarity < 0.4:
                continue

            # Scores multiples
            basic_sim = self.basic_similarity(clean_search, comparison_name)
            pattern2_sim = self.pattern_similarity(clean_search, comparison_name, 2)
            pattern3_sim = self.pattern_similarity(clean_search, comparison_name, 3)

            # Score combiné avec pondération
            combined_score = (basic_sim * 0.4 + 
                            pattern2_sim * 0.3 + 
                            pattern3_sim * 0.3 +
                            char_similarity * 0.1)

            scored_candidates.append((item_name, item_data, combined_score, display_name))

        if not scored_candidates:
            return None, []

        # Trier par score
        scored_candidates.sort(key=lambda x: x[2], reverse=True)

        # Vérifier s'il y a des doublons (même nom sans type)
        best_item = scored_candidates[0]
        best_clean_name = re.sub(r'\([^)]*\)', '', best_item[0]).strip()

        duplicates = []
        for item_name, item_data, score, display_name in scored_candidates[:10]:  # Limiter à 10 pour les performances
            clean_name = re.sub(r'\([^)]*\)', '', item_name).strip()
            if clean_name == best_clean_name and score > 0.3:
                duplicates.append((item_name, item_data))

        # Pénalité pour les items avec même nom mais type différent si pas de type spécifié
        if item_type == "None" and len(duplicates) > 1:
            # Appliquer une pénalité significative
            penalized_score = best_item[2] * 0.3
            best_item = (best_item[0], best_item[1], penalized_score, best_item[3])

        if len(duplicates) > 1:
            return None, duplicates

        return best_item if best_item[2] > 0.3 else None, []

    def create_embed(self, results, added_to_stock=False):
        """Crée l'embed Discord pour afficher les résultats"""
        found_items = [r for r in results if r['found']]
        title = f"Items Added to Stock ({len(found_items)})" if added_to_stock else f"Items Found ({len(found_items)})"

        embed = discord.Embed(
            title=title,
            color=0x00ff00,
            timestamp=datetime.now()
        )

        description_lines = []

        for result in results:
            item_data = result['item_data']
            status_text = f"({result['status']})"

            value = "Not Found"
            demand = "Not Found"

            # Vérifier que item_data n'est pas None avant d'accéder aux clés
            if item_data is not None:
                # Récupération des valeurs avec les bonnes clés (majuscules)
                if result['status'] == "Clean":
                    if 'Cash Value' in item_data:
                        value = item_data['Cash Value']
                    elif 'cash_value' in item_data:  # Fallback pour l'ancien format
                        value = item_data['cash_value']
                elif result['status'] == "Dupe":
                    if 'Duped Value' in item_data:
                        value = item_data['Duped Value']
                    elif 'duped_value' in item_data:  # Fallback pour l'ancien format
                        value = item_data['duped_value']

                # Récupération de la demande
                if 'Demand' in item_data:
                    demand = item_data['Demand']
                elif 'demand' in item_data:  # Fallback pour l'ancien format
                    demand = item_data['demand']

            if result['found'] and not result['multiple']:
                emoji = "✅"
                quantity_text = f" x{result.get('quantity', 1)}" if added_to_stock and result.get('quantity', 1) > 1 else ""
                type_text = f"({result['type']})" if result['type'] != "None" else ""

                description_lines.append(f"{emoji} {result['display_name']} {type_text} {status_text}{quantity_text}")
                description_lines.append(f"├ Value: {value}")
                description_lines.append(f"└ Demand: {demand}")

            elif result['multiple']:
                emoji = "ℹ️"
                type_list = []
                for item in result['duplicates']:
                    type_match = re.search(r'\(([^)]*)\)', item[0])
                    if type_match:
                        type_list.append(type_match.group(1))

                type_display = " / ".join(type_list) if type_list else "Multiple Types"
                status_text = f"({result['status']})" if result['status'] else ""

                description_lines.append(f"{emoji} {result['search_text']} ({type_display}) {status_text}")
                description_lines.append("└ Select the type.")

            else:
                emoji = "❌"
                type_text = f"({result['type']})" if result['type'] != "None" else ""
                status_text = f"({result['status']})" if result['status'] else ""

                description_lines.append(f"{emoji} {result['search_text']} {type_text} {status_text}")
                description_lines.append("├ Value: Not Found")
                description_lines.append("└ Demand: Not Found")

        embed.description = "\n".join(description_lines) if description_lines else "No items processed."
        return embed

    def process_items(self, items_text, add_to_stock=False):
        """Traite la liste d'items et retourne les résultats"""
        items = self.extract_separators(items_text)
        results = []

        for item in items:
            # Extraire la quantité
            quantity, remaining_text = self.extract_quantity(item)

            # Extraire le type
            item_type, remaining_text = self.extract_type(remaining_text)

            # Extraire l'année si c'est un hyperchrome
            year = None
            if item_type == "Hyperchrome":
                year, remaining_text = self.extract_year(remaining_text)

            # Extraire le statut
            status, remaining_text = self.extract_status(remaining_text)

            # Déterminer le statut par défaut pour les hyperchromes
            if item_type == "Hyperchrome" and status == "Clean":
                default_status = self.get_hyperchrome_default_status(year)
                status = default_status

            # Chercher l'item
            best_match, duplicates = self.find_best_match(remaining_text, item_type, year)

            result = {
                'search_text': remaining_text,
                'type': item_type,
                'year': year,
                'status': status,
                'quantity': quantity,
                'found': best_match is not None,
                'multiple': len(duplicates) > 1,
                'duplicates': duplicates,
                'item_data': best_match[1] if best_match else None,
                'display_name': best_match[0] if best_match else remaining_text
            }

            # Ajouter au stock si demandé
            if add_to_stock and best_match:
                self.add_item_to_stock(best_match[0], best_match[1], status, quantity)

            results.append(result)

        return results

# Fonction setup pour intégrer le système dans le bot
def setup_stockage_system(bot):
    """Configure le système de stockage avec le bot"""
    stockage_system = StockageSystem()

    @bot.tree.command(name="add_stock", description="Ajouter des items au stock")
    @app_commands.describe(items="Liste d'items à ajouter (séparés par +, ,, ou and)")
    async def add_stock(interaction: discord.Interaction, items: str):
        """Commande pour ajouter des items au stock"""
        await interaction.response.defer()

        # Recharger les données
        stockage_system.load_data()

        # Traiter les items et les ajouter au stock
        results = stockage_system.process_items(items, add_to_stock=True)

        # Créer l'embed
        embed = stockage_system.create_embed(results, added_to_stock=True)
        if bot.user and bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)

        # Vérifier s'il y a des items multiples
        multiple_items = [r for r in results if r['multiple']]

        if multiple_items:
            # Créer les menus déroulants pour les items multiples
            view = MultipleItemView(multiple_items, results, stockage_system, True)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)

    # Démarrer la mise à jour automatique des valeurs
    async def update_stockage_loop():
        while True:
            await asyncio.sleep(1)  # Actualiser toutes les secondes
            stockage_system.load_data()
            stockage_system.update_stockage_values()

    # Lancer la boucle de mise à jour
    asyncio.create_task(update_stockage_loop())

    return stockage_system

class MultipleItemView(discord.ui.View):
    def __init__(self, multiple_items, all_results, stockage_system, add_to_stock=False):
        super().__init__(timeout=300)
        self.multiple_items = multiple_items
        self.all_results = all_results
        self.stockage_system = stockage_system
        self.add_to_stock = add_to_stock

        for i, item in enumerate(multiple_items):
            if len(item['duplicates']) > 1:
                select = ItemSelect(item, i, self)
                self.add_item(select)

class ItemSelect(discord.ui.Select):
    def __init__(self, item_data, index, parent_view):
        self.item_data = item_data
        self.parent_view = parent_view

        options = []
        for duplicate in item_data['duplicates']:
            item_name = duplicate[0]
            # Extraire le type de l'item
            type_match = re.search(r'\(([^)]*)\)', item_name)
            type_name = type_match.group(1) if type_match else "Unknown"

            options.append(discord.SelectOption(
                label=type_name,
                description=f"Select {type_name}",
                value=f"{index}_{type_name}"
            ))

        super().__init__(
            placeholder=f"Choose type for {item_data['search_text']}",
            options=options,
            custom_id=f"item_select_{index}"
        )

    async def callback(self, interaction: discord.Interaction):
        # Parser la valeur sélectionnée
        index, selected_type = self.values[0].split('_', 1)
        index = int(index)

        # Trouver l'item correspondant
        selected_item = None
        for duplicate in self.item_data['duplicates']:
            if f"({selected_type})" in duplicate[0]:
                selected_item = duplicate
                break

        if selected_item:
            # Mettre à jour le résultat
            for i, result in enumerate(self.parent_view.all_results):
                if result['multiple'] and result['search_text'] == self.item_data['search_text']:
                    updated_result = {
                        'search_text': result['search_text'],
                        'type': selected_type,
                        'year': result['year'],
                        'status': result['status'],
                        'quantity': result['quantity'],
                        'found': True,
                        'multiple': False,
                        'duplicates': [],
                        'item_data': selected_item[1],
                        'display_name': selected_item[0]
                    }

                    # Ajouter au stock si nécessaire
                    if self.parent_view.add_to_stock:
                        self.parent_view.stockage_system.add_item_to_stock(
                            selected_item[0], 
                            selected_item[1], 
                            result['status'], 
                            result['quantity']
                        )

                    self.parent_view.all_results[i] = updated_result
                    break

            # Supprimer ce menu de la vue
            self.parent_view.remove_item(self)
            
            # Créer le nouvel embed
            new_embed = self.parent_view.stockage_system.create_embed(
                self.parent_view.all_results, 
                added_to_stock=self.parent_view.add_to_stock
            )
            if interaction.client.user and interaction.client.user.avatar:
                new_embed.set_thumbnail(url=interaction.client.user.avatar.url)

            # Vérifier s'il reste des menus déroulants
            remaining_selects = [item for item in self.parent_view.children if isinstance(item, ItemSelect)]
            
            if remaining_selects:
                # Il reste des menus, garder la vue avec les menus restants
                await interaction.response.edit_message(embed=new_embed, view=self.parent_view)
            else:
                # Plus de menus, supprimer la vue
                await interaction.response.edit_message(embed=new_embed, view=None)
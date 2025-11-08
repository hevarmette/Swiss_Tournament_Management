from bs4 import BeautifulSoup
import csv
import re
import os
from typing import List, Dict, Optional

def extract_player_data(player_div) -> Optional[Dict[str, str]]:
    """
    Extract player information from a player div element.
    """
    try:
        # Extract name and country code
        name_span = player_div.find('span', class_='name')
        if not name_span:
            return None
        
        # Get the HTML content to preserve <br> structure
        name_html = str(name_span)
        
        # Extract country code using regex from the HTML
        country_match = re.search(r'\[([A-Z]{2})\]', name_html)
        country_code = country_match.group(1) if country_match else ''
        
        # Split by <br> or <br/> tags to separate first and last name
        name_parts = re.split(r'<br\s*/?>', name_html, flags=re.IGNORECASE)
        
        # Clean up the parts
        cleaned_parts = []
        for part in name_parts:
            # Remove HTML tags and clean up
            clean_part = re.sub(r'<[^>]+>', '', part)  # Remove any HTML tags
            clean_part = re.sub(r'\[[A-Z]{2}\]', '', clean_part)  # Remove country code
            clean_part = clean_part.strip()  # Remove whitespace
            if clean_part:  # Only add non-empty parts
                cleaned_parts.append(clean_part)
        
        # Extract first and last name based on cleaned parts
        if len(cleaned_parts) == 0:
            first_name = ''
            last_name = ''
        elif len(cleaned_parts) == 1:
            # Only one part - could be first name only or combined name
            single_part = cleaned_parts[0]
            # Check if it contains spaces (multiple words in one part)
            words = single_part.split()
            if len(words) == 1:
                first_name = words[0]
                last_name = ''
            elif len(words) == 2:
                first_name = words[0]
                last_name = words[1]
            else:  # More than 2 words in single part
                first_name = words[0]
                last_name = ' '.join(words[1:])
        elif len(cleaned_parts) == 2:
            # Two parts separated by <br> - first part is first name, second is last name
            first_name = cleaned_parts[0].strip()
            last_name = cleaned_parts[1].strip()
        else:
            # More than 2 parts - first is first name, combine rest as last name
            first_name = cleaned_parts[0].strip()
            last_name = ' '.join(cleaned_parts[1:]).strip()
        
        # Determine winner/loser status
        classes = player_div.get('class', [])
        if 'winner' in classes:
            status = 'Winner'
        elif 'loser' in classes:
            status = 'Loser'
        else:
            status = 'Unknown'
        
        # Extract match record and points from the div text
        full_text = player_div.get_text()
        
        # Extract match record (pattern: (X-Y-Z))
        record_match = re.search(r'\((\d+-\d+-\d+)\)', full_text)
        match_record = record_match.group(1) if record_match else ''
        
        # Extract points (pattern: X pts)
        points_match = re.search(r'(\d+)\s+pts', full_text)
        points = points_match.group(1) if points_match else ''
        
        return {
            'first_name': first_name,
            'last_name': last_name,
            'country_code': country_code,
            'winner_or_loser': status,
            'match_record': match_record,
            'points': points
        }
    
    except Exception as e:
        print(f"Error extracting player data: {e}")
        return None

def debug_html_structure(soup):
    """
    Debug function to understand the HTML structure.
    """
    print("=== DEBUGGING HTML STRUCTURE ===")
    
    # Check if we got the actual page content
    title = soup.find('title')
    print(f"Page title: {title.get_text() if title else 'No title found'}")
    
    # Look for different possible match row patterns
    patterns_to_check = [
        ('div', {'class': 'row row-cols-3 match no-gutter'}),
        ('div', {'class': lambda x: x and 'match' in ' '.join(x) if x else False}),
        ('div', {'class': lambda x: x and 'row' in ' '.join(x) if x else False}),
        ('div', {'class': lambda x: x and 'player' in ' '.join(x) if x else False}),
    ]
    
    for tag, attrs in patterns_to_check:
        elements = soup.find_all(tag, attrs)
        print(f"Found {len(elements)} elements with pattern: {tag} {attrs}")
        if elements and len(elements) > 0:
            print(f"First element classes: {elements[0].get('class', [])}")
            # Print a sample of the content
            sample_text = elements[0].get_text()[:200]
            print(f"Sample content: {sample_text}")
    
    # Look for any divs with 'match' in class name
    all_match_divs = soup.find_all('div', class_=re.compile(r'match'))
    print(f"Found {len(all_match_divs)} divs with 'match' in class name")
    
    # Look for any spans with 'name' class
    name_spans = soup.find_all('span', class_='name')
    print(f"Found {len(name_spans)} spans with 'name' class")
    if name_spans:
        print(f"First name span content: {name_spans[0]}")  # Show HTML structure
        print(f"First name span text: {name_spans[0].get_text()}")
    
    print("=== END DEBUG INFO ===\n")

def scrape_local_html(file_path: str, debug: bool = True) -> List[Dict[str, str]]:
    """
    Scrape tournament data from a local HTML file.
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found!")
            print("Make sure you've saved the webpage as an HTML file in the same directory as this script.")
            return []
        
        print(f"Reading HTML from: {file_path}")
        
        # Read the HTML file
        with open(file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        print(f"HTML file size: {len(html_content)} characters")
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        if debug:
            debug_html_structure(soup)
        
        # Try multiple selector patterns
        match_selectors = [
            'div.row.row-cols-3.match.no-gutter',
            'div[class*="match"]',
            '.match',
            'div.row[class*="match"]',
            'div[class*="row"][class*="match"]',
        ]
        
        match_rows = []
        for selector in match_selectors:
            try:
                found_rows = soup.select(selector)
                if found_rows:
                    print(f"Found {len(found_rows)} matches using selector: {selector}")
                    match_rows = found_rows
                    break
            except Exception as e:
                print(f"Selector '{selector}' failed: {e}")
        
        if not match_rows:
            print("No match rows found with any selector pattern")
            
            # Let's try a more general approach - look for any div containing player names
            print("Trying alternative approach - looking for player name patterns...")
            all_divs = soup.find_all('div')
            potential_matches = []
            
            for div in all_divs:
                text = div.get_text()
                # Look for the pattern of country codes and match records
                if re.search(r'\[[A-Z]{2}\].*\(\d+-\d+-\d+\)', text):
                    potential_matches.append(div)
            
            print(f"Found {len(potential_matches)} divs with player-like content")
            if potential_matches:
                # Try to find their parent containers
                for match_div in potential_matches[:5]:  # Check first 5
                    parent = match_div.parent
                    if parent and parent not in match_rows:
                        match_rows.append(parent)
            
            print(f"Using {len(match_rows)} potential match containers")
        
        if not match_rows:
            return []
        
        players_data = []
        
        for i, row in enumerate(match_rows):
            print(f"Processing match row {i+1}")
            
            # Try multiple ways to find player divs
            player_selectors = [
                'div[class*="player"]',
                '.player',
                'div.col-5[class*="player"]',
                'div[class*="col"][class*="player"]',
            ]
            
            player_divs = []
            for selector in player_selectors:
                try:
                    found_players = row.select(selector)
                    if found_players:
                        player_divs = found_players
                        print(f"Found players using selector: {selector}")
                        break
                except Exception as e:
                    continue
            
            # If no player divs found with selectors, try finding them by content
            if not player_divs:
                all_divs_in_row = row.find_all('div')
                for div in all_divs_in_row:
                    text = div.get_text()
                    if re.search(r'\[[A-Z]{2}\].*\(\d+-\d+-\d+\)', text):
                        player_divs.append(div)
                
                if player_divs:
                    print(f"Found players by content pattern")
            
            if not player_divs:
                print(f"No player divs found in row {i+1}")
                continue
            
            print(f"Found {len(player_divs)} players in row {i+1}")
            
            for j, player_div in enumerate(player_divs):
                player_data = extract_player_data(player_div)
                if player_data and all(key in player_data for key in ['first_name', 'last_name', 'country_code']):
                    players_data.append(player_data)
                    full_name = f"{player_data['first_name']} {player_data['last_name']}".strip()
                    print(f"Extracted player {j+1}: {full_name} [{player_data['country_code']}]")
                else:
                    print(f"Failed to extract data for player {j+1} in row {i+1}")
                    # Debug: print the div content
                    print(f"Div content: {player_div.get_text()[:100]}...")
                    if player_data:
                        print(f"Partial data extracted: {player_data}")
        
        return players_data
    
    except Exception as e:
        print(f"Error reading/parsing HTML file: {e}")
        return []

def save_to_csv(data: List[Dict[str, str]], filename: str = 'tournament_data.csv'):
    """
    Save the scraped data to a CSV file.
    """
    if not data:
        print("No data to save.")
        return
    
    fieldnames = ['first_name', 'last_name', 'country_code', 'winner_or_loser', 'match_record', 'points']
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        print(f"Data saved to {filename}")
        print(f"Total records: {len(data)}")
    
    except Exception as e:
        print(f"Error saving to CSV: {e}")

def main():
    # List common HTML file names to look for
    possible_files = [
        'tournament_data.html',
        'WCS02wcZg4VXtaqyIk5L.html',
        'pairings.html',
        'rk9.html',
        'index.html',
        'tournament.html'
    ]
    
    # Try to find the HTML file
    html_file = None
    for filename in possible_files:
        if os.path.exists(filename):
            html_file = filename
            break
    
    # If no file found, ask user for the filename
    if not html_file:
        print("HTML file not found. Please make sure you've saved the webpage as an HTML file.")
        print("Looking for files like:", ", ".join(possible_files))
        html_file = input("Enter the name of your saved HTML file: ").strip()
    
    print(f"Using HTML file: {html_file}")
    print("Scraping tournament data from local HTML file...")
    
    players_data = scrape_local_html(html_file, debug=True)
    
    if players_data:
        print(f"\nSuccessfully scraped {len(players_data)} player records")
        
        # First, let's check what keys are in the first few records for debugging
        print("\nDebugging first record keys:")
        if players_data:
            print(f"Keys in first record: {list(players_data[0].keys())}")
            print(f"First record content: {players_data[0]}")
        
        # Display first few records
        print("\nFirst 5 records:")
        for i, player in enumerate(players_data[:5], 1):
            # Safely get values with defaults in case of missing keys
            first_name = player.get('first_name', '')
            last_name = player.get('last_name', '')
            country_code = player.get('country_code', '')
            winner_or_loser = player.get('winner_or_loser', 'Unknown')
            match_record = player.get('match_record', '')
            points = player.get('points', '')
            
            full_name = f"{first_name} {last_name}".strip()
            print(f"{i}. {full_name} [{country_code}] - {winner_or_loser} - {match_record} - {points} pts")
        
        # Save to CSV
        save_to_csv(players_data, "names2.csv")
    else:
        print("No data scraped. Check the debug output above for more information.")

if __name__ == "__main__":
    main()
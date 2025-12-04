"""
Country Mapper Module - ISO3 Code Mapping and Validation

Provides comprehensive mapping between country names, demonyms, aliases,
and ISO 3166-1 alpha-3 codes for international relations analysis.
"""

import re
import logging
from typing import Optional, List, Dict, Set, Tuple

logger = logging.getLogger(__name__)


class CountryMapper:
    """
    Maps country names, demonyms, and aliases to ISO3 codes.
    Supports fuzzy matching and common variations.
    """
    
    def __init__(self):
        """Initialize the country mapper with comprehensive mappings."""
        self._build_mappings()
    
    def _build_mappings(self):
        """Build internal lookup dictionaries."""
        # Primary mapping: ISO3 -> (Official Name, [aliases/demonyms])
        self._countries: Dict[str, Tuple[str, List[str]]] = {
            # North America
            'USA': ('United States of America', [
                'United States', 'US', 'U.S.', 'U.S.A.', 'America', 'American', 
                'Americans', 'Washington D.C.', 'the United States', 'the US',
                'Biden', 'Trump', 'White House'
            ]),
            'CAN': ('Canada', [
                'Canadian', 'Canadians', 'Ottawa', 'Trudeau', 'Canadian government'
            ]),
            'MEX': ('Mexico', [
                'Mexican', 'Mexicans', 'Mexico City', 'Sheinbaum', 'AMLO',
                'López Obrador', 'Mexican government'
            ]),
            
            # Europe - Western
            'GBR': ('United Kingdom', [
                'UK', 'U.K.', 'Britain', 'British', 'Great Britain', 'England',
                'English', 'Scotland', 'Scottish', 'Wales', 'Welsh', 'London',
                'Westminster', 'Downing Street', 'Northern Ireland'
            ]),
            'FRA': ('France', [
                'French', 'Paris', 'Macron', 'Élysée', 'Elysee', 'Francais'
            ]),
            'DEU': ('Germany', [
                'German', 'Germans', 'Berlin', 'Scholz', 'Merkel', 'Bundestag',
                'Deutschland', 'Federal Republic of Germany'
            ]),
            'ITA': ('Italy', [
                'Italian', 'Italians', 'Rome', 'Roma', 'Meloni', 'Italia'
            ]),
            'ESP': ('Spain', [
                'Spanish', 'Spaniard', 'Madrid', 'España', 'Sanchez'
            ]),
            'PRT': ('Portugal', [
                'Portuguese', 'Lisbon', 'Lisboa'
            ]),
            'NLD': ('Netherlands', [
                'Dutch', 'Holland', 'Amsterdam', 'The Hague', 'Den Haag'
            ]),
            'BEL': ('Belgium', [
                'Belgian', 'Brussels', 'Bruxelles', 'Brussel'
            ]),
            'AUT': ('Austria', [
                'Austrian', 'Vienna', 'Wien'
            ]),
            'CHE': ('Switzerland', [
                'Swiss', 'Bern', 'Geneva', 'Genève', 'Zurich', 'Zürich',
                'Helvetia', 'Confederation'
            ]),
            'IRL': ('Ireland', [
                'Irish', 'Dublin', 'Éire', 'Republic of Ireland'
            ]),
            'LUX': ('Luxembourg', [
                'Luxembourgish', 'Luxembourger'
            ]),
            
            # Europe - Northern
            'SWE': ('Sweden', [
                'Swedish', 'Swede', 'Swedes', 'Stockholm'
            ]),
            'NOR': ('Norway', [
                'Norwegian', 'Oslo', 'Norge'
            ]),
            'DNK': ('Denmark', [
                'Danish', 'Dane', 'Danes', 'Copenhagen', 'København'
            ]),
            'FIN': ('Finland', [
                'Finnish', 'Finn', 'Finns', 'Helsinki', 'Suomi'
            ]),
            'ISL': ('Iceland', [
                'Icelandic', 'Icelander', 'Reykjavik', 'Reykjavík'
            ]),
            
            # Europe - Eastern
            'POL': ('Poland', [
                'Polish', 'Pole', 'Poles', 'Warsaw', 'Warszawa', 'Polska'
            ]),
            'CZE': ('Czech Republic', [
                'Czech', 'Czechia', 'Prague', 'Praha'
            ]),
            'SVK': ('Slovakia', [
                'Slovak', 'Slovakian', 'Bratislava'
            ]),
            'HUN': ('Hungary', [
                'Hungarian', 'Budapest', 'Orban', 'Orbán', 'Magyar'
            ]),
            'ROU': ('Romania', [
                'Romanian', 'Bucharest', 'București'
            ]),
            'BGR': ('Bulgaria', [
                'Bulgarian', 'Sofia', 'Sofiya'
            ]),
            'UKR': ('Ukraine', [
                'Ukrainian', 'Ukrainians', 'Kyiv', 'Kiev', 'Zelensky',
                'Zelenskyy', 'Zelenskiy'
            ]),
            'BLR': ('Belarus', [
                'Belarusian', 'Belorussian', 'Minsk', 'Lukashenko'
            ]),
            'MDA': ('Moldova', [
                'Moldovan', 'Chisinau', 'Chișinău'
            ]),
            
            # Europe - Balkans
            'GRC': ('Greece', [
                'Greek', 'Greeks', 'Athens', 'Athina', 'Hellenic'
            ]),
            'SRB': ('Serbia', [
                'Serbian', 'Serb', 'Serbs', 'Belgrade', 'Beograd'
            ]),
            'HRV': ('Croatia', [
                'Croatian', 'Croat', 'Croats', 'Zagreb', 'Hrvatska'
            ]),
            'SVN': ('Slovenia', [
                'Slovenian', 'Slovene', 'Ljubljana'
            ]),
            'BIH': ('Bosnia and Herzegovina', [
                'Bosnian', 'Herzegovinian', 'Sarajevo', 'Bosnia'
            ]),
            'MNE': ('Montenegro', [
                'Montenegrin', 'Podgorica'
            ]),
            'MKD': ('North Macedonia', [
                'Macedonian', 'Skopje', 'Macedonia', 'FYROM'
            ]),
            'ALB': ('Albania', [
                'Albanian', 'Tirana', 'Tiranë'
            ]),
            'XKX': ('Kosovo', [
                'Kosovar', 'Pristina', 'Prishtina', 'Prishtinë'
            ]),
            
            # Europe - Baltic
            'EST': ('Estonia', [
                'Estonian', 'Tallinn', 'Eesti'
            ]),
            'LVA': ('Latvia', [
                'Latvian', 'Riga', 'Latvija'
            ]),
            'LTU': ('Lithuania', [
                'Lithuanian', 'Vilnius', 'Lietuva'
            ]),
            
            # Russia & CIS
            'RUS': ('Russia', [
                'Russian', 'Russians', 'Moscow', 'Moskva', 'Putin', 'Kremlin',
                'Russian Federation', 'RF'
            ]),
            'KAZ': ('Kazakhstan', [
                'Kazakh', 'Astana', 'Nur-Sultan', 'Almaty'
            ]),
            'UZB': ('Uzbekistan', [
                'Uzbek', 'Tashkent'
            ]),
            'TKM': ('Turkmenistan', [
                'Turkmen', 'Ashgabat'
            ]),
            'KGZ': ('Kyrgyzstan', [
                'Kyrgyz', 'Bishkek'
            ]),
            'TJK': ('Tajikistan', [
                'Tajik', 'Dushanbe'
            ]),
            'AZE': ('Azerbaijan', [
                'Azerbaijani', 'Azeri', 'Baku'
            ]),
            'GEO': ('Georgia', [
                'Georgian', 'Tbilisi'  # Note: context-dependent (US state vs country)
            ]),
            'ARM': ('Armenia', [
                'Armenian', 'Yerevan'
            ]),
            
            # Middle East
            'ISR': ('Israel', [
                'Israeli', 'Israelis', 'Tel Aviv', 'Jerusalem', 'Netanyahu',
                'IDF', 'Knesset'
            ]),
            'PSE': ('Palestine', [
                'Palestinian', 'Palestinians', 'Gaza', 'West Bank', 'Ramallah',
                'Hamas', 'Palestinian Authority', 'PA'
            ]),
            'LBN': ('Lebanon', [
                'Lebanese', 'Beirut', 'Hezbollah'
            ]),
            'SYR': ('Syria', [
                'Syrian', 'Syrians', 'Damascus', 'Assad'
            ]),
            'JOR': ('Jordan', [
                'Jordanian', 'Amman'
            ]),
            'IRQ': ('Iraq', [
                'Iraqi', 'Iraqis', 'Baghdad'
            ]),
            'IRN': ('Iran', [
                'Iranian', 'Iranians', 'Tehran', 'Khamenei', 'Persian',
                'Islamic Republic of Iran'
            ]),
            'SAU': ('Saudi Arabia', [
                'Saudi', 'Saudis', 'Riyadh', 'MBS', 'Mohammed bin Salman',
                'Kingdom of Saudi Arabia', 'KSA'
            ]),
            'ARE': ('United Arab Emirates', [
                'UAE', 'Emirati', 'Emirates', 'Dubai', 'Abu Dhabi'
            ]),
            'QAT': ('Qatar', [
                'Qatari', 'Doha'
            ]),
            'KWT': ('Kuwait', [
                'Kuwaiti', 'Kuwait City'
            ]),
            'BHR': ('Bahrain', [
                'Bahraini', 'Manama'
            ]),
            'OMN': ('Oman', [
                'Omani', 'Muscat'
            ]),
            'YEM': ('Yemen', [
                'Yemeni', 'Sanaa', "Sana'a", 'Houthi', 'Houthis'
            ]),
            'TUR': ('Turkey', [
                'Turkish', 'Turk', 'Turks', 'Ankara', 'Istanbul', 'Erdogan',
                'Erdoğan', 'Türkiye'
            ]),
            'CYP': ('Cyprus', [
                'Cypriot', 'Nicosia'
            ]),
            
            # Asia - East
            'CHN': ('China', [
                'Chinese', 'Beijing', 'Peking', 'PRC', "People's Republic of China",
                'Xi Jinping', 'Xi', 'CCP', 'Communist Party of China'
            ]),
            'JPN': ('Japan', [
                'Japanese', 'Tokyo', 'Nippon', 'Nihon'
            ]),
            'KOR': ('South Korea', [
                'Korean', 'South Korean', 'Seoul', 'Republic of Korea', 'ROK'
            ]),
            'PRK': ('North Korea', [
                'North Korean', 'Pyongyang', 'DPRK', "Democratic People's Republic of Korea",
                'Kim Jong Un', 'Kim Jong-un'
            ]),
            'TWN': ('Taiwan', [
                'Taiwanese', 'Taipei', 'Republic of China', 'ROC'
            ]),
            'MNG': ('Mongolia', [
                'Mongolian', 'Ulaanbaatar'
            ]),
            'HKG': ('Hong Kong', [
                'Hong Konger', 'HK'
            ]),
            'MAC': ('Macau', [
                'Macanese', 'Macao'
            ]),
            
            # Asia - Southeast
            'VNM': ('Vietnam', [
                'Vietnamese', 'Hanoi', 'Ho Chi Minh City', 'Saigon'
            ]),
            'THA': ('Thailand', [
                'Thai', 'Bangkok', 'Siam'
            ]),
            'PHL': ('Philippines', [
                'Filipino', 'Philippine', 'Filipinos', 'Manila', 'Duterte', 'Marcos'
            ]),
            'IDN': ('Indonesia', [
                'Indonesian', 'Jakarta'
            ]),
            'MYS': ('Malaysia', [
                'Malaysian', 'Kuala Lumpur', 'KL'
            ]),
            'SGP': ('Singapore', [
                'Singaporean'
            ]),
            'MMR': ('Myanmar', [
                'Burmese', 'Burma', 'Naypyidaw', 'Rangoon', 'Yangon'
            ]),
            'KHM': ('Cambodia', [
                'Cambodian', 'Khmer', 'Phnom Penh'
            ]),
            'LAO': ('Laos', [
                'Laotian', 'Lao', 'Vientiane'
            ]),
            'BRN': ('Brunei', [
                'Bruneian', 'Bandar Seri Begawan'
            ]),
            'TLS': ('Timor-Leste', [
                'East Timorese', 'East Timor', 'Dili'
            ]),
            
            # Asia - South
            'IND': ('India', [
                'Indian', 'Indians', 'New Delhi', 'Delhi', 'Modi', 'BJP'
            ]),
            'PAK': ('Pakistan', [
                'Pakistani', 'Pakistanis', 'Islamabad', 'Karachi'
            ]),
            'BGD': ('Bangladesh', [
                'Bangladeshi', 'Dhaka'
            ]),
            'LKA': ('Sri Lanka', [
                'Sri Lankan', 'Colombo', 'Ceylon'
            ]),
            'NPL': ('Nepal', [
                'Nepali', 'Nepalese', 'Kathmandu'
            ]),
            'BTN': ('Bhutan', [
                'Bhutanese', 'Thimphu'
            ]),
            'MDV': ('Maldives', [
                'Maldivian', 'Male', 'Malé'
            ]),
            'AFG': ('Afghanistan', [
                'Afghan', 'Afghans', 'Kabul', 'Taliban'
            ]),
            
            # Oceania
            'AUS': ('Australia', [
                'Australian', 'Australians', 'Canberra', 'Sydney', 'Melbourne'
            ]),
            'NZL': ('New Zealand', [
                'New Zealander', 'Kiwi', 'Kiwis', 'Wellington', 'Auckland'
            ]),
            'PNG': ('Papua New Guinea', [
                'Papua New Guinean', 'Port Moresby'
            ]),
            'FJI': ('Fiji', [
                'Fijian', 'Suva'
            ]),
            
            # Africa - North
            'EGY': ('Egypt', [
                'Egyptian', 'Egyptians', 'Cairo', 'Sisi', 'el-Sisi'
            ]),
            'LBY': ('Libya', [
                'Libyan', 'Tripoli', 'Benghazi'
            ]),
            'TUN': ('Tunisia', [
                'Tunisian', 'Tunis'
            ]),
            'DZA': ('Algeria', [
                'Algerian', 'Algiers'
            ]),
            'MAR': ('Morocco', [
                'Moroccan', 'Rabat', 'Casablanca'
            ]),
            'SDN': ('Sudan', [
                'Sudanese', 'Khartoum'
            ]),
            'SSD': ('South Sudan', [
                'South Sudanese', 'Juba'
            ]),
            
            # Africa - Sub-Saharan
            'NGA': ('Nigeria', [
                'Nigerian', 'Nigerians', 'Abuja', 'Lagos'
            ]),
            'ZAF': ('South Africa', [
                'South African', 'Pretoria', 'Cape Town', 'Johannesburg'
            ]),
            'KEN': ('Kenya', [
                'Kenyan', 'Nairobi'
            ]),
            'ETH': ('Ethiopia', [
                'Ethiopian', 'Addis Ababa'
            ]),
            'GHA': ('Ghana', [
                'Ghanaian', 'Accra'
            ]),
            'TZA': ('Tanzania', [
                'Tanzanian', 'Dodoma', 'Dar es Salaam'
            ]),
            'UGA': ('Uganda', [
                'Ugandan', 'Kampala'
            ]),
            'RWA': ('Rwanda', [
                'Rwandan', 'Kigali'
            ]),
            'COD': ('Democratic Republic of the Congo', [
                'Congolese', 'DRC', 'DR Congo', 'Kinshasa', 'Democratic Republic of Congo'
            ]),
            'COG': ('Republic of the Congo', [
                'Congolese', 'Brazzaville', 'Congo-Brazzaville'
            ]),
            'AGO': ('Angola', [
                'Angolan', 'Luanda'
            ]),
            'MOZ': ('Mozambique', [
                'Mozambican', 'Maputo'
            ]),
            'ZWE': ('Zimbabwe', [
                'Zimbabwean', 'Harare'
            ]),
            'ZMB': ('Zambia', [
                'Zambian', 'Lusaka'
            ]),
            'BWA': ('Botswana', [
                'Motswana', 'Batswana', 'Gaborone'
            ]),
            'NAM': ('Namibia', [
                'Namibian', 'Windhoek'
            ]),
            'SEN': ('Senegal', [
                'Senegalese', 'Dakar'
            ]),
            'CIV': ('Ivory Coast', [
                'Ivorian', "Côte d'Ivoire", 'Cote d Ivoire', 'Abidjan', 'Yamoussoukro'
            ]),
            'CMR': ('Cameroon', [
                'Cameroonian', 'Yaoundé', 'Yaounde'
            ]),
            'MLI': ('Mali', [
                'Malian', 'Bamako'
            ]),
            'BFA': ('Burkina Faso', [
                'Burkinabe', 'Ouagadougou'
            ]),
            'NER': ('Niger', [
                'Nigerien', 'Niamey'
            ]),
            'TCD': ('Chad', [
                'Chadian', "N'Djamena", 'Ndjamena'
            ]),
            'SOM': ('Somalia', [
                'Somali', 'Mogadishu'
            ]),
            'ERI': ('Eritrea', [
                'Eritrean', 'Asmara'
            ]),
            'DJI': ('Djibouti', [
                'Djiboutian'
            ]),
            
            # South America
            'BRA': ('Brazil', [
                'Brazilian', 'Brazilians', 'Brasilia', 'Brasília', 'São Paulo',
                'Sao Paulo', 'Lula'
            ]),
            'ARG': ('Argentina', [
                'Argentine', 'Argentinian', 'Buenos Aires', 'Milei'
            ]),
            'COL': ('Colombia', [
                'Colombian', 'Bogota', 'Bogotá'
            ]),
            'PER': ('Peru', [
                'Peruvian', 'Lima'
            ]),
            'VEN': ('Venezuela', [
                'Venezuelan', 'Caracas', 'Maduro'
            ]),
            'CHL': ('Chile', [
                'Chilean', 'Santiago'
            ]),
            'ECU': ('Ecuador', [
                'Ecuadorian', 'Quito', 'Guayaquil'
            ]),
            'BOL': ('Bolivia', [
                'Bolivian', 'La Paz', 'Sucre'
            ]),
            'PRY': ('Paraguay', [
                'Paraguayan', 'Asunción', 'Asuncion'
            ]),
            'URY': ('Uruguay', [
                'Uruguayan', 'Montevideo'
            ]),
            'GUY': ('Guyana', [
                'Guyanese', 'Georgetown'
            ]),
            'SUR': ('Suriname', [
                'Surinamese', 'Paramaribo'
            ]),
            
            # Central America & Caribbean
            'CUB': ('Cuba', [
                'Cuban', 'Havana', 'Habana'
            ]),
            'HTI': ('Haiti', [
                'Haitian', 'Port-au-Prince'
            ]),
            'DOM': ('Dominican Republic', [
                'Dominican', 'Santo Domingo'
            ]),
            'JAM': ('Jamaica', [
                'Jamaican', 'Kingston'
            ]),
            'PAN': ('Panama', [
                'Panamanian', 'Panama City'
            ]),
            'CRI': ('Costa Rica', [
                'Costa Rican', 'San José', 'San Jose'
            ]),
            'GTM': ('Guatemala', [
                'Guatemalan', 'Guatemala City'
            ]),
            'HND': ('Honduras', [
                'Honduran', 'Tegucigalpa'
            ]),
            'SLV': ('El Salvador', [
                'Salvadoran', 'San Salvador', 'Bukele'
            ]),
            'NIC': ('Nicaragua', [
                'Nicaraguan', 'Managua', 'Ortega'
            ]),
            'BLZ': ('Belize', [
                'Belizean', 'Belmopan'
            ]),
            
            # Special entities (often used in international relations)
            'VAT': ('Vatican City', [
                'Vatican', 'Holy See', 'Pope', 'Papal'
            ]),
        }
        
        # Build reverse lookup (lowercase name/alias -> ISO3)
        self._name_to_iso3: Dict[str, str] = {}
        for iso3, (name, aliases) in self._countries.items():
            # Add official name
            self._name_to_iso3[name.lower()] = iso3
            self._name_to_iso3[iso3.lower()] = iso3
            # Add all aliases
            for alias in aliases:
                self._name_to_iso3[alias.lower()] = iso3
        
        # Build set of valid ISO3 codes
        self._valid_iso3: Set[str] = set(self._countries.keys())
    
    def get_iso3(self, name: str) -> Optional[str]:
        """
        Get ISO3 code from country name, demonym, or alias.
        
        Args:
            name: Country name, demonym, capital, or alias
        
        Returns:
            ISO3 code if found, None otherwise
        """
        if not name:
            return None
        
        # Clean the input
        cleaned = name.strip()
        
        # Direct ISO3 match (case-insensitive)
        if cleaned.upper() in self._valid_iso3:
            return cleaned.upper()
        
        # Lookup in mappings
        return self._name_to_iso3.get(cleaned.lower())
    
    def is_valid_iso3(self, code: str) -> bool:
        """Check if a code is a valid ISO3 country code."""
        return code.upper() in self._valid_iso3 if code else False
    
    def get_country_name(self, iso3: str) -> Optional[str]:
        """Get official country name from ISO3 code."""
        if iso3.upper() in self._countries:
            return self._countries[iso3.upper()][0]
        return None
    
    def normalize_actor_list(self, actors: List[str]) -> List[str]:
        """
        Normalize a list of country references to ISO3 codes.
        
        Args:
            actors: List of country names, codes, or aliases
        
        Returns:
            List of unique, valid ISO3 codes
        """
        iso3_codes = set()
        for actor in actors:
            if not actor:
                continue
            # Handle comma-separated values
            parts = actor.replace(',', ' ').split()
            for part in parts:
                code = self.get_iso3(part.strip())
                if code:
                    iso3_codes.add(code)
        return sorted(list(iso3_codes))
    
    def extract_countries_from_text(self, text: str) -> List[str]:
        """
        Extract country mentions from free text.
        
        Args:
            text: Text to scan for country mentions
        
        Returns:
            List of unique ISO3 codes found in the text
        """
        if not text:
            return []
        
        text_lower = text.lower()
        found_countries = set()
        
        # Check for each country and its aliases
        for iso3, (name, aliases) in self._countries.items():
            # Check official name
            if name.lower() in text_lower:
                found_countries.add(iso3)
                continue
            
            # Check aliases (word boundary match for short aliases)
            for alias in aliases:
                alias_lower = alias.lower()
                # For short aliases (2-3 chars), require word boundaries
                if len(alias) <= 3:
                    pattern = rf'\b{re.escape(alias_lower)}\b'
                    if re.search(pattern, text_lower):
                        found_countries.add(iso3)
                        break
                else:
                    if alias_lower in text_lower:
                        found_countries.add(iso3)
                        break
        
        return sorted(list(found_countries))
    
    def parse_actor_field(self, field_value: str) -> List[str]:
        """
        Parse an actor field value (may contain multiple ISO3 codes).
        
        Args:
            field_value: String like "USA", "USA, CHN", or "['USA', 'CHN']"
        
        Returns:
            List of ISO3 codes
        """
        if not field_value or field_value in ('', '[]', "['']"):
            return []
        
        # Handle JSON-like arrays
        if field_value.startswith('['):
            # Remove brackets and quotes
            cleaned = field_value.strip('[]').replace("'", "").replace('"', '')
            parts = [p.strip() for p in cleaned.split(',')]
        else:
            # Split by comma
            parts = [p.strip() for p in field_value.split(',')]
        
        # Convert to ISO3 and filter valid codes
        result = []
        for part in parts:
            if part:
                code = self.get_iso3(part)
                if code:
                    result.append(code)
                elif self.is_valid_iso3(part):
                    result.append(part.upper())
        
        return result
    
    def get_all_countries(self) -> Dict[str, str]:
        """Get dictionary of all ISO3 codes to country names."""
        return {iso3: data[0] for iso3, data in self._countries.items()}


# Global instance for convenience
_mapper = None

def get_mapper() -> CountryMapper:
    """Get or create global CountryMapper instance."""
    global _mapper
    if _mapper is None:
        _mapper = CountryMapper()
    return _mapper


def get_iso3(name: str) -> Optional[str]:
    """Convenience function to get ISO3 code."""
    return get_mapper().get_iso3(name)


def normalize_actors(actors: List[str]) -> List[str]:
    """Convenience function to normalize actor list."""
    return get_mapper().normalize_actor_list(actors)


def extract_countries(text: str) -> List[str]:
    """Convenience function to extract countries from text."""
    return get_mapper().extract_countries_from_text(text)


if __name__ == "__main__":
    # Test the mapper
    mapper = CountryMapper()
    
    test_cases = [
        "USA", "United States", "American", "Biden",
        "CHN", "China", "Chinese", "Beijing",
        "GBR", "UK", "British", "London",
        "DEU", "Germany", "German",
        "Ukrainian", "Zelensky",
        "Invalid", ""
    ]
    
    print("Country Mapper Test Results:")
    print("=" * 50)
    for test in test_cases:
        result = mapper.get_iso3(test)
        name = mapper.get_country_name(result) if result else "Not found"
        print(f"  '{test}' -> {result} ({name})")
    
    # Test text extraction
    sample_text = """
    The United States and China announced new trade negotiations today.
    German Chancellor and French President met in Berlin to discuss EU policy.
    Russian forces continue operations while Ukrainian defenses hold.
    """
    
    print("\nText Extraction Test:")
    print("=" * 50)
    countries = mapper.extract_countries_from_text(sample_text)
    print(f"Found countries: {countries}")
    for iso3 in countries:
        print(f"  {iso3}: {mapper.get_country_name(iso3)}")


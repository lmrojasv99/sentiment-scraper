"""
Country Mapper Module — ISO3 Code Mapping and Text Extraction

Maps country names, demonyms, capitals, and common aliases to
ISO 3166-1 alpha-3 codes.

Key improvements:
  - Complete UN 193 + observer-state coverage (~240 entries)
  - Pre-compiled per-country regex patterns for fast text scanning
  - unidecode normalization for accent-insensitive matching
  - Three-layer extraction: official name → aliases → demonyms
"""

import re
import logging
from typing import Optional, List, Dict, Set, Tuple

logger = logging.getLogger(__name__)


class CountryMapper:
    """Maps country names, demonyms, and aliases to ISO3 codes."""

    def __init__(self):
        self._build_mappings()
        # Compiled patterns are built lazily on first extract call
        self._alias_patterns: Optional[Dict[str, re.Pattern]] = None
        self._norm_func = None

    # ------------------------------------------------------------------
    # Data: ISO3 -> (Official Name, [aliases / demonyms / capitals])
    # ------------------------------------------------------------------

    def _build_mappings(self):
        self._countries: Dict[str, Tuple[str, List[str]]] = {

            # ── North America ──────────────────────────────────────────
            'USA': ('United States of America', [
                'United States', 'US', 'U.S.', 'U.S.A.', 'America', 'American',
                'Americans', 'Washington', 'Washington DC', 'White House', 'Pentagon',
                'Capitol Hill', 'State Department',
            ]),
            'CAN': ('Canada', [
                'Canadian', 'Canadians', 'Ottawa', 'Toronto',
            ]),
            'MEX': ('Mexico', [
                'Mexican', 'Mexicans', 'Mexico City', 'Tlatelolco',
            ]),

            # ── Europe — Western ──────────────────────────────────────
            'GBR': ('United Kingdom', [
                'UK', 'U.K.', 'Britain', 'British', 'Great Britain', 'England',
                'English', 'Scotland', 'Scottish', 'Wales', 'Welsh', 'London',
                'Westminster', 'Downing Street', 'Northern Ireland', 'Buckingham Palace',
            ]),
            'FRA': ('France', [
                'French', 'Paris', 'Macron', 'Elysee', 'Quai d Orsay',
            ]),
            'DEU': ('Germany', [
                'German', 'Germans', 'Berlin', 'Bundestag', 'Deutschland',
                'Federal Republic of Germany',
            ]),
            'ITA': ('Italy', [
                'Italian', 'Italians', 'Rome', 'Roma', 'Meloni', 'Italia', 'Quirinal',
            ]),
            'ESP': ('Spain', [
                'Spanish', 'Spaniard', 'Madrid', 'Moncloa', 'Zarzuela',
            ]),
            'PRT': ('Portugal', [
                'Portuguese', 'Lisbon', 'Lisboa',
            ]),
            'NLD': ('Netherlands', [
                'Dutch', 'Holland', 'Amsterdam', 'The Hague', 'Den Haag',
            ]),
            'BEL': ('Belgium', [
                'Belgian', 'Brussels', 'Bruxelles', 'Brussel',
            ]),
            'AUT': ('Austria', [
                'Austrian', 'Vienna', 'Wien',
            ]),
            'CHE': ('Switzerland', [
                'Swiss', 'Bern', 'Geneva', 'Zurich', 'Helvetia',
            ]),
            'IRL': ('Ireland', [
                'Irish', 'Dublin',
            ]),
            'LUX': ('Luxembourg', [
                'Luxembourgish', 'Luxembourger',
            ]),
            'AND': ('Andorra', [
                'Andorran',
            ]),
            'MCO': ('Monaco', [
                'Monacan',
            ]),
            'SMR': ('San Marino', [
                'Sammarinese',
            ]),
            'LIE': ('Liechtenstein', [
                'Liechtensteiner',
            ]),
            'MLT': ('Malta', [
                'Maltese', 'Valletta',
            ]),

            # ── Europe — Northern ─────────────────────────────────────
            'SWE': ('Sweden', [
                'Swedish', 'Swede', 'Swedes', 'Stockholm',
            ]),
            'NOR': ('Norway', [
                'Norwegian', 'Oslo', 'Norge',
            ]),
            'DNK': ('Denmark', [
                'Danish', 'Dane', 'Danes', 'Copenhagen',
            ]),
            'FIN': ('Finland', [
                'Finnish', 'Finn', 'Finns', 'Helsinki', 'Suomi',
            ]),
            'ISL': ('Iceland', [
                'Icelandic', 'Icelander', 'Reykjavik',
            ]),

            # ── Europe — Eastern ─────────────────────────────────────
            'POL': ('Poland', [
                'Polish', 'Pole', 'Poles', 'Warsaw', 'Warszawa',
            ]),
            'CZE': ('Czech Republic', [
                'Czech', 'Czechia', 'Prague', 'Praha',
            ]),
            'SVK': ('Slovakia', [
                'Slovak', 'Slovakian', 'Bratislava',
            ]),
            'HUN': ('Hungary', [
                'Hungarian', 'Budapest', 'Orban', 'Magyar',
            ]),
            'ROU': ('Romania', [
                'Romanian', 'Bucharest',
            ]),
            'BGR': ('Bulgaria', [
                'Bulgarian', 'Sofia',
            ]),
            'UKR': ('Ukraine', [
                'Ukrainian', 'Ukrainians', 'Kyiv', 'Kiev', 'Zelensky', 'Zelenskyy',
            ]),
            'BLR': ('Belarus', [
                'Belarusian', 'Belorussian', 'Minsk', 'Lukashenko',
            ]),
            'MDA': ('Moldova', [
                'Moldovan', 'Chisinau', 'Transnistria',
            ]),

            # ── Europe — Balkans ──────────────────────────────────────
            'GRC': ('Greece', [
                'Greek', 'Greeks', 'Athens', 'Hellenic',
            ]),
            'SRB': ('Serbia', [
                'Serbian', 'Serb', 'Serbs', 'Belgrade', 'Beograd',
            ]),
            'HRV': ('Croatia', [
                'Croatian', 'Croat', 'Croats', 'Zagreb', 'Hrvatska',
            ]),
            'SVN': ('Slovenia', [
                'Slovenian', 'Slovene', 'Ljubljana',
            ]),
            'BIH': ('Bosnia and Herzegovina', [
                'Bosnian', 'Sarajevo', 'Bosnia', 'Republika Srpska',
            ]),
            'MNE': ('Montenegro', [
                'Montenegrin', 'Podgorica',
            ]),
            'MKD': ('North Macedonia', [
                'Macedonian', 'Skopje', 'Macedonia', 'FYROM',
            ]),
            'ALB': ('Albania', [
                'Albanian', 'Tirana',
            ]),
            'XKX': ('Kosovo', [
                'Kosovar', 'Pristina', 'Prishtina',
            ]),

            # ── Europe — Baltic ───────────────────────────────────────
            'EST': ('Estonia', [
                'Estonian', 'Tallinn',
            ]),
            'LVA': ('Latvia', [
                'Latvian', 'Riga',
            ]),
            'LTU': ('Lithuania', [
                'Lithuanian', 'Vilnius',
            ]),

            # ── Russia & CIS ─────────────────────────────────────────
            'RUS': ('Russia', [
                'Russian', 'Russians', 'Moscow', 'Putin', 'Kremlin',
                'Russian Federation',
            ]),
            'KAZ': ('Kazakhstan', [
                'Kazakh', 'Kazakhstani', 'Astana', 'Almaty',
            ]),
            'UZB': ('Uzbekistan', [
                'Uzbek', 'Uzbekistani', 'Tashkent',
            ]),
            'TKM': ('Turkmenistan', [
                'Turkmen', 'Ashgabat',
            ]),
            'KGZ': ('Kyrgyzstan', [
                'Kyrgyz', 'Kyrgyzstani', 'Bishkek',
            ]),
            'TJK': ('Tajikistan', [
                'Tajik', 'Tajikistani', 'Dushanbe',
            ]),
            'AZE': ('Azerbaijan', [
                'Azerbaijani', 'Azeri', 'Baku',
            ]),
            'GEO': ('Georgia', [
                'Georgian', 'Tbilisi',
            ]),
            'ARM': ('Armenia', [
                'Armenian', 'Yerevan',
            ]),

            # ── Middle East ───────────────────────────────────────────
            'ISR': ('Israel', [
                'Israeli', 'Israelis', 'Tel Aviv', 'Jerusalem', 'Netanyahu',
                'IDF', 'Knesset',
            ]),
            'PSE': ('Palestine', [
                'Palestinian', 'Palestinians', 'Gaza', 'West Bank', 'Ramallah',
                'Hamas', 'Palestinian Authority',
            ]),
            'LBN': ('Lebanon', [
                'Lebanese', 'Beirut', 'Hezbollah',
            ]),
            'SYR': ('Syria', [
                'Syrian', 'Syrians', 'Damascus', 'Assad',
            ]),
            'JOR': ('Jordan', [
                'Jordanian', 'Amman',
            ]),
            'IRQ': ('Iraq', [
                'Iraqi', 'Iraqis', 'Baghdad',
            ]),
            'IRN': ('Iran', [
                'Iranian', 'Iranians', 'Tehran', 'Khamenei', 'Persian',
                'Islamic Republic of Iran',
            ]),
            'SAU': ('Saudi Arabia', [
                'Saudi', 'Saudis', 'Riyadh', 'MBS', 'Mohammed bin Salman',
                'Kingdom of Saudi Arabia', 'KSA',
            ]),
            'ARE': ('United Arab Emirates', [
                'UAE', 'Emirati', 'Emirates', 'Dubai', 'Abu Dhabi',
            ]),
            'QAT': ('Qatar', [
                'Qatari', 'Doha',
            ]),
            'KWT': ('Kuwait', [
                'Kuwaiti', 'Kuwait City',
            ]),
            'BHR': ('Bahrain', [
                'Bahraini', 'Manama',
            ]),
            'OMN': ('Oman', [
                'Omani', 'Muscat',
            ]),
            'YEM': ('Yemen', [
                'Yemeni', 'Sanaa', 'Houthi', 'Houthis',
            ]),
            'TUR': ('Turkey', [
                'Turkish', 'Turk', 'Turks', 'Ankara', 'Istanbul', 'Erdogan', 'Turkiye',
            ]),
            'CYP': ('Cyprus', [
                'Cypriot', 'Nicosia',
            ]),
            'VAT': ('Vatican City', [
                'Vatican', 'Holy See', 'Pope', 'Papal',
            ]),

            # ── Asia — East ───────────────────────────────────────────
            'CHN': ('China', [
                'Chinese', 'Beijing', 'Peking', 'PRC', 'Peoples Republic of China',
                'Xi Jinping', 'CCP', 'Communist Party of China', 'Zhongnanhai',
                'Mainland China',
            ]),
            'JPN': ('Japan', [
                'Japanese', 'Tokyo', 'Nippon', 'Nihon',
            ]),
            'KOR': ('South Korea', [
                'Korean', 'South Korean', 'Seoul', 'Republic of Korea', 'ROK',
                'Blue House',
            ]),
            'PRK': ('North Korea', [
                'North Korean', 'Pyongyang', 'DPRK',
                'Democratic Peoples Republic of Korea', 'Kim Jong Un',
            ]),
            'TWN': ('Taiwan', [
                'Taiwanese', 'Taipei', 'Republic of China', 'ROC',
            ]),
            'MNG': ('Mongolia', [
                'Mongolian', 'Ulaanbaatar', 'Ulan Bator',
            ]),

            # ── Asia — Southeast ─────────────────────────────────────
            'VNM': ('Vietnam', [
                'Vietnamese', 'Hanoi', 'Ho Chi Minh City', 'Saigon',
            ]),
            'THA': ('Thailand', [
                'Thai', 'Bangkok', 'Siam',
            ]),
            'PHL': ('Philippines', [
                'Filipino', 'Philippine', 'Filipinos', 'Manila', 'Marcos',
            ]),
            'IDN': ('Indonesia', [
                'Indonesian', 'Jakarta',
            ]),
            'MYS': ('Malaysia', [
                'Malaysian', 'Kuala Lumpur',
            ]),
            'SGP': ('Singapore', [
                'Singaporean',
            ]),
            'MMR': ('Myanmar', [
                'Burmese', 'Burma', 'Naypyidaw', 'Yangon', 'Rangoon',
            ]),
            'KHM': ('Cambodia', [
                'Cambodian', 'Khmer', 'Phnom Penh',
            ]),
            'LAO': ('Laos', [
                'Laotian', 'Lao', 'Vientiane',
            ]),
            'BRN': ('Brunei', [
                'Bruneian', 'Bandar Seri Begawan',
            ]),
            'TLS': ('Timor-Leste', [
                'East Timorese', 'East Timor', 'Dili',
            ]),

            # ── Asia — South ─────────────────────────────────────────
            'IND': ('India', [
                'Indian', 'Indians', 'New Delhi', 'Delhi', 'Modi', 'BJP',
            ]),
            'PAK': ('Pakistan', [
                'Pakistani', 'Pakistanis', 'Islamabad', 'Karachi',
            ]),
            'BGD': ('Bangladesh', [
                'Bangladeshi', 'Dhaka',
            ]),
            'LKA': ('Sri Lanka', [
                'Sri Lankan', 'Colombo', 'Ceylon',
            ]),
            'NPL': ('Nepal', [
                'Nepali', 'Nepalese', 'Kathmandu',
            ]),
            'BTN': ('Bhutan', [
                'Bhutanese', 'Thimphu',
            ]),
            'MDV': ('Maldives', [
                'Maldivian', 'Male',
            ]),
            'AFG': ('Afghanistan', [
                'Afghan', 'Afghans', 'Kabul', 'Taliban',
            ]),

            # ── Oceania ───────────────────────────────────────────────
            'AUS': ('Australia', [
                'Australian', 'Australians', 'Canberra', 'Sydney', 'Melbourne',
            ]),
            'NZL': ('New Zealand', [
                'New Zealander', 'Kiwi', 'Kiwis', 'Wellington', 'Auckland',
            ]),
            'PNG': ('Papua New Guinea', [
                'Papua New Guinean', 'Port Moresby',
            ]),
            'FJI': ('Fiji', [
                'Fijian', 'Suva',
            ]),
            'SLB': ('Solomon Islands', [
                'Solomon Islander', 'Honiara',
            ]),
            'VUT': ('Vanuatu', [
                'Vanuatuan', 'Port Vila',
            ]),
            'WSM': ('Samoa', [
                'Samoan', 'Apia',
            ]),
            'TON': ('Tonga', [
                'Tongan', 'Nuku alofa',
            ]),
            'KIR': ('Kiribati', [
                'Kiribati', 'Tarawa',
            ]),
            'FSM': ('Micronesia', [
                'Micronesian', 'Palikir',
            ]),
            'MHL': ('Marshall Islands', [
                'Marshallese', 'Majuro',
            ]),
            'PLW': ('Palau', [
                'Palauan', 'Ngerulmud',
            ]),
            'NRU': ('Nauru', [
                'Nauruan', 'Yaren',
            ]),
            'TUV': ('Tuvalu', [
                'Tuvaluan', 'Funafuti',
            ]),

            # ── Africa — North ────────────────────────────────────────
            'EGY': ('Egypt', [
                'Egyptian', 'Egyptians', 'Cairo', 'Sisi',
            ]),
            'LBY': ('Libya', [
                'Libyan', 'Tripoli', 'Benghazi',
            ]),
            'TUN': ('Tunisia', [
                'Tunisian', 'Tunis',
            ]),
            'DZA': ('Algeria', [
                'Algerian', 'Algiers',
            ]),
            'MAR': ('Morocco', [
                'Moroccan', 'Rabat', 'Casablanca',
            ]),
            'SDN': ('Sudan', [
                'Sudanese', 'Khartoum',
            ]),
            'SSD': ('South Sudan', [
                'South Sudanese', 'Juba',
            ]),

            # ── Africa — Sub-Saharan ──────────────────────────────────
            'NGA': ('Nigeria', [
                'Nigerian', 'Nigerians', 'Abuja', 'Lagos',
            ]),
            'ZAF': ('South Africa', [
                'South African', 'Pretoria', 'Cape Town', 'Johannesburg',
            ]),
            'KEN': ('Kenya', [
                'Kenyan', 'Nairobi',
            ]),
            'ETH': ('Ethiopia', [
                'Ethiopian', 'Addis Ababa',
            ]),
            'GHA': ('Ghana', [
                'Ghanaian', 'Accra',
            ]),
            'TZA': ('Tanzania', [
                'Tanzanian', 'Dodoma', 'Dar es Salaam',
            ]),
            'UGA': ('Uganda', [
                'Ugandan', 'Kampala',
            ]),
            'RWA': ('Rwanda', [
                'Rwandan', 'Kigali',
            ]),
            'COD': ('Democratic Republic of the Congo', [
                'Congolese', 'DRC', 'DR Congo', 'Kinshasa',
                'Democratic Republic of Congo', 'Congo Kinshasa',
            ]),
            'COG': ('Republic of the Congo', [
                'Brazzaville', 'Congo Brazzaville',
            ]),
            'AGO': ('Angola', [
                'Angolan', 'Luanda',
            ]),
            'MOZ': ('Mozambique', [
                'Mozambican', 'Maputo',
            ]),
            'ZWE': ('Zimbabwe', [
                'Zimbabwean', 'Harare',
            ]),
            'ZMB': ('Zambia', [
                'Zambian', 'Lusaka',
            ]),
            'BWA': ('Botswana', [
                'Motswana', 'Batswana', 'Botswanan', 'Gaborone',
            ]),
            'NAM': ('Namibia', [
                'Namibian', 'Windhoek',
            ]),
            'SEN': ('Senegal', [
                'Senegalese', 'Dakar',
            ]),
            'CIV': ('Ivory Coast', [
                'Ivorian', 'Cote d Ivoire', 'Abidjan', 'Yamoussoukro',
            ]),
            'CMR': ('Cameroon', [
                'Cameroonian', 'Yaounde',
            ]),
            'MLI': ('Mali', [
                'Malian', 'Bamako',
            ]),
            'BFA': ('Burkina Faso', [
                'Burkinabe', 'Ouagadougou',
            ]),
            'NER': ('Niger', [
                'Nigerien', 'Niamey',
            ]),
            'TCD': ('Chad', [
                'Chadian', 'N Djamena', 'Ndjamena',
            ]),
            'SOM': ('Somalia', [
                'Somali', 'Mogadishu',
            ]),
            'ERI': ('Eritrea', [
                'Eritrean', 'Asmara',
            ]),
            'DJI': ('Djibouti', [
                'Djiboutian',
            ]),
            'MDG': ('Madagascar', [
                'Malagasy', 'Antananarivo',
            ]),
            'MWI': ('Malawi', [
                'Malawian', 'Lilongwe',
            ]),
            'MRT': ('Mauritania', [
                'Mauritanian', 'Nouakchott',
            ]),
            'MUS': ('Mauritius', [
                'Mauritian', 'Port Louis',
            ]),
            'STP': ('Sao Tome and Principe', [
                'Santomean',
            ]),
            'SYC': ('Seychelles', [
                'Seychellois', 'Victoria',
            ]),
            'SLE': ('Sierra Leone', [
                'Sierra Leonean', 'Freetown',
            ]),
            'TGO': ('Togo', [
                'Togolese', 'Lome',
            ]),
            'BDI': ('Burundi', [
                'Burundian', 'Gitega', 'Bujumbura',
            ]),
            'GAB': ('Gabon', [
                'Gabonese', 'Libreville',
            ]),
            'BEN': ('Benin', [
                'Beninese', 'Porto Novo', 'Cotonou',
            ]),
            'COM': ('Comoros', [
                'Comorian', 'Moroni',
            ]),
            'GNQ': ('Equatorial Guinea', [
                'Equatorial Guinean', 'Malabo',
            ]),
            'SWZ': ('Eswatini', [
                'Swazi', 'Swaziland', 'Mbabane',
            ]),
            'GMB': ('Gambia', [
                'Gambian', 'Banjul',
            ]),
            'GNB': ('Guinea-Bissau', [
                'Guinea Bissauan',
            ]),
            'GIN': ('Guinea', [
                'Guinean', 'Conakry',
            ]),
            'LSO': ('Lesotho', [
                'Basotho', 'Maseru',
            ]),
            'LBR': ('Liberia', [
                'Liberian', 'Monrovia',
            ]),
            'CPV': ('Cape Verde', [
                'Cabo Verde', 'Cabo Verdean', 'Cape Verdean', 'Praia',
            ]),
            'CAF': ('Central African Republic', [
                'Central African', 'Bangui',
            ]),

            # ── South America ─────────────────────────────────────────
            'BRA': ('Brazil', [
                'Brazilian', 'Brazilians', 'Brasilia', 'Sao Paulo', 'Lula',
            ]),
            'ARG': ('Argentina', [
                'Argentine', 'Argentinian', 'Buenos Aires', 'Milei', 'Casa Rosada',
            ]),
            'COL': ('Colombia', [
                'Colombian', 'Bogota',
            ]),
            'PER': ('Peru', [
                'Peruvian', 'Lima',
            ]),
            'VEN': ('Venezuela', [
                'Venezuelan', 'Caracas', 'Maduro', 'Miraflores',
            ]),
            'CHL': ('Chile', [
                'Chilean', 'Santiago', 'La Moneda',
            ]),
            'ECU': ('Ecuador', [
                'Ecuadorian', 'Quito', 'Guayaquil',
            ]),
            'BOL': ('Bolivia', [
                'Bolivian', 'La Paz', 'Sucre',
            ]),
            'PRY': ('Paraguay', [
                'Paraguayan', 'Asuncion',
            ]),
            'URY': ('Uruguay', [
                'Uruguayan', 'Montevideo',
            ]),
            'GUY': ('Guyana', [
                'Guyanese', 'Georgetown',
            ]),
            'SUR': ('Suriname', [
                'Surinamese', 'Paramaribo',
            ]),

            # ── Central America & Caribbean ───────────────────────────
            'CUB': ('Cuba', [
                'Cuban', 'Havana', 'Habana',
            ]),
            'HTI': ('Haiti', [
                'Haitian', 'Port au Prince',
            ]),
            'DOM': ('Dominican Republic', [
                'Dominican', 'Santo Domingo',
            ]),
            'JAM': ('Jamaica', [
                'Jamaican', 'Kingston',
            ]),
            'TTO': ('Trinidad and Tobago', [
                'Trinidadian', 'Tobagonian', 'Port of Spain',
            ]),
            'PAN': ('Panama', [
                'Panamanian', 'Panama City',
            ]),
            'CRI': ('Costa Rica', [
                'Costa Rican', 'San Jose',
            ]),
            'GTM': ('Guatemala', [
                'Guatemalan', 'Guatemala City',
            ]),
            'HND': ('Honduras', [
                'Honduran', 'Tegucigalpa',
            ]),
            'SLV': ('El Salvador', [
                'Salvadoran', 'San Salvador', 'Bukele',
            ]),
            'NIC': ('Nicaragua', [
                'Nicaraguan', 'Managua', 'Ortega',
            ]),
            'BLZ': ('Belize', [
                'Belizean', 'Belmopan',
            ]),
            'ATG': ('Antigua and Barbuda', [
                'Antiguan', 'Barbudan',
            ]),
            'BHS': ('Bahamas', [
                'Bahamian', 'Nassau',
            ]),
            'BRB': ('Barbados', [
                'Barbadian', 'Bridgetown',
            ]),
            'DMA': ('Dominica', [
                'Dominican', 'Roseau',
            ]),
            'GRD': ('Grenada', [
                'Grenadian', 'Saint Georges',
            ]),
            'KNA': ('Saint Kitts and Nevis', [
                'Kittitian', 'Nevisian',
            ]),
            'LCA': ('Saint Lucia', [
                'Saint Lucian', 'Castries',
            ]),
            'VCT': ('Saint Vincent and the Grenadines', [
                'Vincentian', 'Kingstown',
            ]),
        }

        # Build reverse lookup: lowercase name/alias → ISO3
        self._name_to_iso3: Dict[str, str] = {}
        for iso3, (name, aliases) in self._countries.items():
            self._name_to_iso3[name.lower()] = iso3
            self._name_to_iso3[iso3.lower()] = iso3
            for alias in aliases:
                self._name_to_iso3[alias.lower()] = iso3

        self._valid_iso3: Set[str] = set(self._countries.keys())

    # ------------------------------------------------------------------
    # Pattern compilation (lazy)
    # ------------------------------------------------------------------

    def _ensure_patterns(self):
        """Build per-country compiled regex patterns on first call."""
        if self._alias_patterns is not None:
            return

        from unidecode import unidecode

        def _norm(s: str) -> str:
            s = unidecode(str(s)).lower()
            s = re.sub(r"[^a-z0-9\s]", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        self._norm_func = _norm
        self._alias_patterns = {}

        for iso3, (name, aliases) in self._countries.items():
            terms = [name] + aliases
            # Normalize, deduplicate, sort longest-first so more specific
            # matches take precedence in the alternation
            norm_terms = list(dict.fromkeys(_norm(t) for t in terms if t.strip()))
            norm_terms.sort(key=len, reverse=True)
            pattern_str = r"\b(" + "|".join(re.escape(t) for t in norm_terms if t) + r")\b"
            self._alias_patterns[iso3] = re.compile(pattern_str, re.IGNORECASE)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_iso3(self, name: str) -> Optional[str]:
        """Return ISO3 code for a country name, demonym, capital, or alias."""
        if not name:
            return None
        cleaned = name.strip()
        if cleaned.upper() in self._valid_iso3:
            return cleaned.upper()
        return self._name_to_iso3.get(cleaned.lower())

    def is_valid_iso3(self, code: str) -> bool:
        """Return True if the code is a known ISO3 country code."""
        return code.upper() in self._valid_iso3 if code else False

    def get_country_name(self, iso3: str) -> Optional[str]:
        """Return official country name for an ISO3 code."""
        entry = self._countries.get(iso3.upper() if iso3 else "")
        return entry[0] if entry else None

    def extract_countries_from_text(self, text: str) -> List[str]:
        """Extract ISO3 codes for all countries mentioned in *text*.

        Uses pre-compiled regex patterns with unidecode normalization for
        accent-insensitive, word-boundary matching.
        """
        if not text:
            return []
        self._ensure_patterns()
        norm_text = self._norm_func(text)
        found = set()
        for iso3, pattern in self._alias_patterns.items():
            if pattern.search(norm_text):
                found.add(iso3)
        return sorted(found)

    def normalize_actor_list(self, actors: List[str]) -> List[str]:
        """Normalize a list of country references to sorted ISO3 codes."""
        iso3_codes = set()
        for actor in actors:
            if not actor:
                continue
            for part in actor.replace(',', ' ').split():
                code = self.get_iso3(part.strip())
                if code:
                    iso3_codes.add(code)
        return sorted(iso3_codes)

    def parse_actor_field(self, field_value: str) -> List[str]:
        """Parse an actor field like 'USA', 'USA, CHN', or "['USA', 'CHN']"."""
        if not field_value or field_value in ('', '[]', "['']"):
            return []
        if field_value.startswith('['):
            cleaned = field_value.strip('[]').replace("'", "").replace('"', '')
            parts = [p.strip() for p in cleaned.split(',')]
        else:
            parts = [p.strip() for p in field_value.split(',')]
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
        """Return {ISO3: official_name} for all known countries."""
        return {iso3: data[0] for iso3, data in self._countries.items()}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_mapper: Optional[CountryMapper] = None


def get_mapper() -> CountryMapper:
    """Return (or lazily create) the global CountryMapper instance."""
    global _mapper
    if _mapper is None:
        _mapper = CountryMapper()
    return _mapper


def get_iso3(name: str) -> Optional[str]:
    return get_mapper().get_iso3(name)


def normalize_actors(actors: List[str]) -> List[str]:
    return get_mapper().normalize_actor_list(actors)


def extract_countries(text: str) -> List[str]:
    return get_mapper().extract_countries_from_text(text)

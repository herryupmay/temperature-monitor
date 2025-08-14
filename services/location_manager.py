"""
Location Manager Service for Temperature Monitor
Enhanced with Clever Logger format support and intelligent location discovery
"""

import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Fuzzy matching libraries
try:
    from fuzzywuzzy import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class LocationInfo:
    """Data class for location information"""
    name: str
    confidence: str  # 'high', 'medium', 'low'
    configured: bool = False
    location_type: str = 'unknown'  # 'fridge', 'room', 'freezer', 'custom'
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None
    first_seen: str = None
    last_seen: str = None
    source_count: int = 1
    
    def __post_init__(self):
        if self.first_seen is None:
            self.first_seen = datetime.now().isoformat()
        self.last_seen = datetime.now().isoformat()

class LocationManager:
    """Service for managing temperature monitoring locations with auto-discovery"""
    
    def __init__(self, config_manager=None):
        """Initialize location manager"""
        self.config_manager = config_manager
        self.discovered_locations = {}  # Dict[str, LocationInfo]
        
        # Enhanced location patterns for better detection
        self.location_patterns = [
            # Fridge/Refrigerator patterns
            r'(main|primary|central|pharmacy)\s*(?:fridge|refrigerator|ref)',
            r'(vaccine|medicine|drug)\s*(?:fridge|refrigerator|storage)',
            r'(fridge|refrigerator)\s*([a-z0-9]*)',
            r'(?:fridge|refrigerator)\s*(main|primary|central|[a-z0-9]+)',
            
            # Room/Area patterns  
            r'(storage|pharmacy|medicine|drug)\s*(?:room|area|zone)',
            r'(room|area|zone)\s*([a-z0-9]*)',
            r'(?:room|area)\s*(storage|pharmacy|medicine|[a-z0-9]+)',
            
            # Freezer patterns
            r'(main|primary|backup)\s*freezer',
            r'freezer\s*([a-z0-9]*)',
            
            # Sensor/Channel patterns
            r'(?:sensor|probe|channel|monitor)\s*([a-z0-9]+)',
            r'(sensor|probe|channel)\s*([a-z0-9]*)',
            
            # Specific pharmacy equipment
            r'(vaccine|insulin|medication)\s*(?:storage|fridge|cabinet)',
            r'(controlled|schedule)\s*(?:drug|substance)\s*(?:storage|cabinet)',
        ]
        
        # Temperature threshold hints by location type
        self.default_thresholds = {
            'fridge': {'min': 2.0, 'max': 8.0},
            'freezer': {'min': -25.0, 'max': -15.0},
            'room': {'min': 0.0, 'max': 25.0},  # Medicine storage, not comfort
            'vaccine': {'min': 2.0, 'max': 8.0},
            'insulin': {'min': 2.0, 'max': 8.0},
            'controlled': {'min': 0.0, 'max': 25.0},  # Medicine storage
            'custom': {'min': 0.0, 'max': 30.0}
        }
        
        # Load existing discovered locations if config manager available
        try:
            if self.config_manager and hasattr(self.config_manager, 'load_discovered_locations'):
                self.load_discovered_locations()
            else:
                logger.info("No config manager available - starting with empty locations")
        except Exception as e:
            logger.warning(f"Could not load discovered locations: {e}")
    
    def extract_locations_from_text(self, text: str, filename: str = "") -> List[Dict]:
        """Enhanced location extraction for Clever Logger format"""
        if not text:
            return []
        
        # Try Clever Logger format first
        clever_logger_locations = self.extract_clever_logger_locations(text, filename)
        if clever_logger_locations:
            return clever_logger_locations
        
        # Fallback to original pattern-based extraction
        return self.extract_locations_from_text_fallback(text, filename)
    
    def extract_clever_logger_locations(self, text: str, filename: str = "") -> List[Dict]:
        """Extract locations from Clever Logger format PDFs"""
        locations_found = []
        lines = text.split('\n')
        current_location_info = None
        
        for line_num, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            if not line:
                continue
            
            # Look for Location Details sections
            if line == 'Location Details':
                current_location_info = {}
                continue
            
            # Extract location information from structured format
            if current_location_info is not None:
                if line.startswith('Name') and 'name' not in current_location_info:
                    # Get location name from next non-empty line
                    for next_idx in range(line_num + 1, min(line_num + 5, len(lines))):
                        if next_idx < len(lines):
                            next_line = lines[next_idx].strip()
                            if (next_line and 
                                next_line not in ['Description', 'Device', 'Device Model', 'Log Interval', 'View Location', 'Temperature'] and
                                not next_line.startswith('S/N:') and 
                                not next_line.startswith('CLT-')):
                                current_location_info['name'] = next_line
                                break
                
                elif line.startswith('Description'):
                    # Get description from next line
                    if line_num + 1 < len(lines):
                        desc = lines[line_num + 1].strip()
                        if desc and desc not in ['Device', 'Device Model']:
                            current_location_info['description'] = desc
                
                elif 'Alarm Threshold' in line and 'Low Temperature' in ' '.join(lines[max(0, line_num-2):line_num+1]):
                    # Extract low temperature threshold
                    temp_match = re.search(r'(\d+\.?\d*)\s*°C', line)
                    if temp_match:
                        current_location_info['min_temp'] = float(temp_match.group(1))
                
                elif 'Alarm Threshold' in line and 'High Temperature' in ' '.join(lines[max(0, line_num-2):line_num+1]):
                    # Extract high temperature threshold  
                    temp_match = re.search(r'(\d+\.?\d*)\s*°C', line)
                    if temp_match:
                        current_location_info['max_temp'] = float(temp_match.group(1))
                
                # End of location section - process collected info
                elif line == 'Temperature' and 'name' in current_location_info:
                    location_name = current_location_info['name']
                    description = current_location_info.get('description', '')
                    
                    # Determine location type
                    location_type = self.determine_clever_logger_location_type(location_name, description)
                    
                    # Determine confidence (high for structured Clever Logger data)
                    confidence = 'high'
                    
                    location_info = {
                        'name': location_name,
                        'type': location_type,
                        'confidence': confidence,
                        'min_temp': current_location_info.get('min_temp'),
                        'max_temp': current_location_info.get('max_temp'),
                        'description': description,
                        'context': f"Clever Logger device: {location_name}",
                        'source': filename,
                        'line_number': line_num + 1
                    }
                    
                    locations_found.append(location_info)
                    logger.info(f"Extracted Clever Logger location: {location_name} ({location_type})")
                    
                    # Reset for next location
                    current_location_info = None
        
        return self.deduplicate_locations(locations_found)
    
    def determine_clever_logger_location_type(self, location_name: str, description: str = "") -> str:
        """Determine location type for Clever Logger devices"""
        name_lower = location_name.lower()
        desc_lower = description.lower()
        combined = f"{name_lower} {desc_lower}".strip()
        
        # Check for fridge/refrigeration indicators
        if any(term in combined for term in ['fridge', 'refrigerator', 'vaccine', 'medicine', 'drug']):
            if any(term in combined for term in ['vaccine', 'immunization']):
                return 'vaccine'
            return 'fridge'
        
        # Check for freezer indicators
        if any(term in combined for term in ['freezer', 'frozen']):
            return 'freezer'
        
        # Check for room temperature indicators
        if any(term in combined for term in ['room', 'dispensary', 'pharmacy', 'office', 'storage']):
            return 'room'
        
        # Default based on typical temperature ranges (will be determined from actual readings)
        return 'custom'
    
    def extract_locations_from_text_fallback(self, text: str, filename: str = "") -> List[Dict]:
        """Fallback location extraction method (original implementation)"""
        locations_found = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            original_line = line
            line = line.strip().lower()
            
            if not line:
                continue
            
            # Try each location pattern
            for pattern in self.location_patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                
                for match in matches:
                    # Extract location name from match groups
                    location_parts = [group for group in match.groups() if group and group.strip()]
                    
                    if not location_parts:
                        continue
                    
                    # Build location name
                    raw_location = ' '.join(location_parts).strip()
                    location_name = self.normalize_location_name(raw_location)
                    
                    if not location_name or len(location_name) < 2:
                        continue
                    
                    # Determine location type and confidence
                    location_type = self.determine_location_type(original_line, location_name)
                    confidence = self.calculate_confidence(original_line, location_name, filename)
                    
                    # Extract context around this location for temperature thresholds
                    context = self.get_line_context(lines, line_num, 3)
                    temp_thresholds = self.extract_location_thresholds(context, location_type)
                    
                    location_info = {
                        'name': location_name,
                        'type': location_type,
                        'confidence': confidence,
                        'min_temp': temp_thresholds.get('min'),
                        'max_temp': temp_thresholds.get('max'),
                        'context': original_line[:100],
                        'source': filename,
                        'line_number': line_num + 1
                    }
                    
                    locations_found.append(location_info)
        
        # Deduplicate and merge similar locations
        unique_locations = self.deduplicate_locations(locations_found)
        
        logger.info(f"Extracted {len(unique_locations)} unique locations from text")
        return unique_locations
    
    def normalize_location_name(self, raw_name: str) -> str:
        """Normalize location name for consistency"""
        if not raw_name:
            return ""
        
        # Clean up the name
        name = raw_name.strip().lower()
        
        # Remove common filler words
        filler_words = ['the', 'a', 'an', 'of', 'for', 'at', 'in', 'on']
        words = [w for w in name.split() if w not in filler_words]
        
        if not words:
            return ""
        
        # Standardize common terms
        standardizations = {
            'fridge': 'Fridge',
            'refrigerator': 'Fridge', 
            'ref': 'Fridge',
            'freezer': 'Freezer',
            'room': 'Room',
            'area': 'Area',
            'zone': 'Zone',
            'storage': 'Storage',
            'vaccine': 'Vaccine',
            'medicine': 'Medicine',
            'drug': 'Drug',
            'pharmacy': 'Pharmacy',
            'main': 'Main',
            'primary': 'Primary',
            'central': 'Central',
            'backup': 'Backup'
        }
        
        # Apply standardizations
        standardized_words = []
        for word in words:
            standardized_words.append(standardizations.get(word, word.title()))
        
        return ' '.join(standardized_words)
    
    def determine_location_type(self, line: str, location_name: str) -> str:
        """Determine the type of location based on context"""
        line_lower = line.lower()
        name_lower = location_name.lower()
        
        # Check for specific type indicators
        if any(term in line_lower or term in name_lower for term in ['fridge', 'refrigerator']):
            if any(term in line_lower or term in name_lower for term in ['vaccine', 'insulin']):
                return 'vaccine'
            return 'fridge'
        
        if any(term in line_lower or term in name_lower for term in ['freezer']):
            return 'freezer'
        
        if any(term in line_lower or term in name_lower for term in ['room', 'area', 'zone']):
            return 'room'
        
        if any(term in line_lower or term in name_lower for term in ['vaccine']):
            return 'vaccine'
        
        if any(term in line_lower or term in name_lower for term in ['insulin']):
            return 'insulin'
        
        if any(term in line_lower or term in name_lower for term in ['controlled', 'schedule']):
            return 'controlled'
        
        return 'custom'
    
    def calculate_confidence(self, line: str, location_name: str, filename: str = "") -> str:
        """Calculate confidence score for location detection"""
        score = 0
        
        # Base score for finding a location
        score += 30
        
        # Bonus for explicit location indicators
        line_lower = line.lower()
        if any(term in line_lower for term in ['temperature', 'temp', 'monitoring']):
            score += 20
        
        # Bonus for specific location types
        if any(term in line_lower for term in ['fridge', 'refrigerator', 'freezer']):
            score += 25
        
        # Bonus for pharmacy-specific terms
        if any(term in line_lower for term in ['vaccine', 'medicine', 'drug', 'pharmacy']):
            score += 20
        
        # Bonus for temperature values nearby
        if re.search(r'\d+\.?\d*\s*[°]?[cf]', line_lower):
            score += 15
        
        # Bonus for structured report indicators
        if any(term in line_lower for term in ['daily', 'report', 'summary', 'log']):
            score += 10
        
        # Bonus for clear naming patterns
        if re.search(r'(main|primary|backup|vaccine|storage)', location_name.lower()):
            score += 15
        
        # Penalty for very generic names
        if location_name.lower() in ['fridge', 'room', 'area', 'storage']:
            score -= 15
        
        # Bonus for PDF source (usually more structured)
        if filename.lower().endswith('.pdf'):
            score += 10
        
        # Convert score to confidence level
        if score >= 70:
            return 'high'
        elif score >= 45:
            return 'medium'
        else:
            return 'low'
    
    def get_line_context(self, lines: List[str], line_num: int, context_size: int = 3) -> str:
        """Get context around a specific line for better analysis"""
        start = max(0, line_num - context_size)
        end = min(len(lines), line_num + context_size + 1)
        
        context_lines = []
        for i in range(start, end):
            if i < len(lines):
                context_lines.append(lines[i].strip())
        
        return ' '.join(context_lines)
    
    def extract_location_thresholds(self, context: str, location_type: str) -> Dict[str, Optional[float]]:
        """Extract temperature thresholds specific to this location"""
        thresholds = {'min': None, 'max': None}
        
        if not context:
            return thresholds
        
        context_lower = context.lower()
        
        # Look for explicit min/max statements
        min_match = re.search(r'min(?:imum)?[:\s]*([+-]?\d+\.?\d*)', context_lower)
        max_match = re.search(r'max(?:imum)?[:\s]*([+-]?\d+\.?\d*)', context_lower)
        
        if min_match:
            try:
                thresholds['min'] = float(min_match.group(1))
            except ValueError:
                pass
        
        if max_match:
            try:
                thresholds['max'] = float(max_match.group(1))
            except ValueError:
                pass
        
        # Look for range patterns "2°C - 8°C" or "between 2 and 8"
        range_patterns = [
            r'([+-]?\d+\.?\d*)\s*[°]?[cf]?\s*[-–—]\s*([+-]?\d+\.?\d*)\s*[°]?[cf]?',
            r'between\s+([+-]?\d+\.?\d*)\s+and\s+([+-]?\d+\.?\d*)',
            r'from\s+([+-]?\d+\.?\d*)\s+to\s+([+-]?\d+\.?\d*)'
        ]
        
        for pattern in range_patterns:
            range_match = re.search(pattern, context_lower)
            if range_match:
                try:
                    temp1 = float(range_match.group(1))
                    temp2 = float(range_match.group(2))
                    thresholds['min'] = min(temp1, temp2)
                    thresholds['max'] = max(temp1, temp2)
                    break
                except ValueError:
                    continue
        
        # If no explicit thresholds found, use defaults based on location type
        if thresholds['min'] is None or thresholds['max'] is None:
            defaults = self.default_thresholds.get(location_type, self.default_thresholds['custom'])
            if thresholds['min'] is None:
                thresholds['min'] = defaults['min']
            if thresholds['max'] is None:
                thresholds['max'] = defaults['max']
        
        return thresholds
    
    def deduplicate_locations(self, locations: List[Dict]) -> List[Dict]:
        """Remove exact duplicates while preserving original names from PDFs"""
        if not locations:
            return locations
        
        unique_locations = []
        seen_names = set()
        
        for location in locations:
            location_name = location['name']
            
            # Only remove exact duplicates (same name, same source)
            location_key = (location_name, location.get('source', ''))
            
            if location_key not in seen_names:
                seen_names.add(location_key)
                unique_locations.append(location)
            else:
                # Merge info if exact duplicate found
                for existing in unique_locations:
                    if (existing['name'] == location_name and 
                        existing.get('source') == location.get('source')):
                        self.merge_location_info(existing, location)
                        break
        
        return unique_locations
    
    def merge_location_info(self, existing: Dict, new: Dict):
        """Merge information from two similar locations"""
        # Use the higher confidence name
        if new['confidence'] == 'high' and existing['confidence'] != 'high':
            existing['name'] = new['name']
        
        # Use the better confidence score
        confidence_priority = {'high': 3, 'medium': 2, 'low': 1}
        if confidence_priority.get(new['confidence'], 0) > confidence_priority.get(existing['confidence'], 0):
            existing['confidence'] = new['confidence']
        
        # Use more specific temperature thresholds if available
        if new.get('min_temp') is not None and existing.get('min_temp') is None:
            existing['min_temp'] = new['min_temp']
        
        if new.get('max_temp') is not None and existing.get('max_temp') is None:
            existing['max_temp'] = new['max_temp']
        
        # Prefer more specific location types
        type_priority = {'vaccine': 5, 'insulin': 4, 'fridge': 3, 'freezer': 3, 'room': 2, 'custom': 1}
        if type_priority.get(new['type'], 0) > type_priority.get(existing['type'], 0):
            existing['type'] = new['type']
    
    def register_discovered_location(self, location_info: Dict) -> str:
        """Register a newly discovered location (preserve exact names from PDFs)"""
        location_name = location_info['name']
        
        # Check if this exact location already exists
        if location_name in self.discovered_locations:
            # Update existing location
            existing_location = self.discovered_locations[location_name]
            existing_location.last_seen = datetime.now().isoformat()
            existing_location.source_count += 1
            
            # Update confidence if better
            confidence_priority = {'high': 3, 'medium': 2, 'low': 1}
            if confidence_priority.get(location_info['confidence'], 0) > confidence_priority.get(existing_location.confidence, 0):
                existing_location.confidence = location_info['confidence']
            
            logger.info(f"Updated existing location: {location_name}")
            return location_name
        else:
            # Always create new location with exact name from PDF
            new_location = LocationInfo(
                name=location_name,
                confidence=location_info['confidence'],
                location_type=location_info.get('type', 'custom'),
                min_temp=location_info.get('min_temp'),
                max_temp=location_info.get('max_temp')
            )
            
            self.discovered_locations[location_name] = new_location
            logger.info(f"Registered new location: {location_name}")
            return location_name
    
    def merge_locations_by_user_choice(self, source_key: str, target_key: str) -> bool:
        """Merge two locations when user decides they're the same"""
        if source_key not in self.discovered_locations or target_key not in self.discovered_locations:
            return False
        
        source_location = self.discovered_locations[source_key]
        target_location = self.discovered_locations[target_key]
        
        # Merge source into target
        target_location.source_count += source_location.source_count
        target_location.last_seen = max(source_location.last_seen, target_location.last_seen)
        
        # Use better confidence
        confidence_priority = {'high': 3, 'medium': 2, 'low': 1}
        if confidence_priority.get(source_location.confidence, 0) > confidence_priority.get(target_location.confidence, 0):
            target_location.confidence = source_location.confidence
        
        # Remove source location
        del self.discovered_locations[source_key]
        
        logger.info(f"Merged location '{source_key}' into '{target_key}' by user choice")
        return True
    
    def get_potential_matches(self, location_name: str, threshold: int = 70) -> List[Dict]:
        """Get potential matching locations for user to decide (non-aggressive)"""
        if not FUZZY_AVAILABLE or not self.discovered_locations:
            return []
        
        existing_names = list(self.discovered_locations.keys())
        matches = process.extract(location_name.lower(), 
                                [name.lower() for name in existing_names], 
                                limit=3)
        
        potential_matches = []
        for match in matches:
            if match[1] >= threshold and match[1] < 95:  # Don't include near-exact matches
                # Find the original key
                for key in existing_names:
                    if key.lower() == match[0]:
                        location = self.discovered_locations[key]
                        potential_matches.append({
                            'key': key,
                            'name': location.name,
                            'similarity': match[1],
                            'type': location.location_type,
                            'configured': location.configured
                        })
                        break
        
        return potential_matches
    
    def find_similar_location(self, location_name: str, threshold: int = 95) -> Optional[str]:
        """Find very similar existing location (only near-exact matches)"""
        if not FUZZY_AVAILABLE or not self.discovered_locations:
            return None
        
        existing_names = list(self.discovered_locations.keys())
        
        # Only match very high similarity to avoid false positives
        matches = process.extractOne(location_name.lower(), 
                                   [name.lower() for name in existing_names])
        
        if matches and matches[1] >= threshold:
            # Find the exact key that matched
            for key in existing_names:
                if key.lower() == matches[0]:
                    return key
        
        return None
    
    def get_discovered_locations(self) -> Dict[str, Dict]:
        """Get all discovered locations as dictionary"""
        result = {}
        for key, location in self.discovered_locations.items():
            result[key] = {
                'name': location.name,
                'confidence': location.confidence,
                'configured': location.configured,
                'type': location.location_type,
                'min_temp': location.min_temp,
                'max_temp': location.max_temp,
                'first_seen': location.first_seen,
                'last_seen': location.last_seen,
                'source_count': location.source_count
            }
        return result
    
    def mark_location_configured(self, location_key: str, config: Dict):
        """Mark a location as configured by user"""
        if location_key in self.discovered_locations:
            location = self.discovered_locations[location_key]
            location.configured = True
            location.location_type = config.get('type', location.location_type)
            location.min_temp = config.get('min_temp', location.min_temp)
            location.max_temp = config.get('max_temp', location.max_temp)
            
            logger.info(f"Marked location as configured: {location_key}")
            return True
        return False
    
    def save_discovered_locations(self):
        """Save discovered locations to configuration"""
        try:
            if self.config_manager and hasattr(self.config_manager, 'save_discovered_locations'):
                locations_data = self.get_discovered_locations()
                self.config_manager.save_discovered_locations(locations_data)
            else:
                logger.info("No config manager - cannot save discovered locations")
        except Exception as e:
            logger.warning(f"Could not save discovered locations: {e}")
    
    def load_discovered_locations(self):
        """Load discovered locations from configuration"""
        try:
            if self.config_manager and hasattr(self.config_manager, 'load_discovered_locations'):
                locations_data = self.config_manager.load_discovered_locations()
                
                for key, data in locations_data.items():
                    location = LocationInfo(
                        name=data['name'],
                        confidence=data['confidence'],
                        configured=data.get('configured', False),
                        location_type=data.get('type', 'custom'),
                        min_temp=data.get('min_temp'),
                        max_temp=data.get('max_temp'),
                        first_seen=data.get('first_seen'),
                        last_seen=data.get('last_seen'),
                        source_count=data.get('source_count', 1)
                    )
                    self.discovered_locations[key] = location
            else:
                logger.info("No config manager - starting with empty discovered locations")
        except Exception as e:
            logger.warning(f"Could not load discovered locations: {e}")
    
    def get_unconfigured_locations(self) -> List[Dict]:
        """Get locations that need user configuration"""
        unconfigured = []
        for key, location in self.discovered_locations.items():
            if not location.configured:
                unconfigured.append({
                    'key': key,
                    'name': location.name,
                    'confidence': location.confidence,
                    'type': location.location_type,
                    'min_temp': location.min_temp,
                    'max_temp': location.max_temp,
                    'source_count': location.source_count
                })
        
        # Sort by confidence and source count
        unconfigured.sort(key=lambda x: (
            {'high': 3, 'medium': 2, 'low': 1}[x['confidence']], 
            x['source_count']
        ), reverse=True)
        
        return unconfigured
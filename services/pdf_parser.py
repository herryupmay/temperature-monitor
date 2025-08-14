#!/usr/bin/env python3
"""
PDF Temperature Parser Service
Clean, dedicated service for parsing Clever Logger temperature PDFs
"""

import re
import io
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# PDF processing libraries
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    try:
        import pdfplumber
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

logger = logging.getLogger(__name__)

class PDFTemperatureParser:
    """
    Clean, focused parser for Clever Logger temperature PDFs
    Handles the exact format: Location Details -> Name -> Recordings
    """
    
    def __init__(self):
        """Initialize the PDF parser"""
        if not PDF_AVAILABLE:
            logger.warning("No PDF processing library available. Install PyPDF2 or pdfplumber.")
    
    def parse_pdf_data(self, pdf_data: bytes, filename: str = "report.pdf") -> Dict:
        """
        Main parsing method - extracts all temperature data from PDF
        
        Args:
            pdf_data: Raw PDF bytes
            filename: Source filename for reference
            
        Returns:
            Dict with locations, temperatures, and summary data
        """
        try:
            # Extract text from PDF
            text_content = self._extract_text_from_pdf(pdf_data)
            
            if not text_content.strip():
                logger.warning(f"No text extracted from PDF: {filename}")
                return self._empty_result()
            
            # Parse the structured content
            locations = self._extract_locations(text_content)
            temperatures = self._extract_temperatures(text_content, locations)
            daily_summary = self._create_daily_summary(temperatures, filename)
            
            result = {
                'locations': locations,
                'temperatures': temperatures,
                'daily_summary': daily_summary,
                'source': filename,
                'text_length': len(text_content),
                'success': True
            }
            
            logger.info(f"Parsed PDF '{filename}': {len(locations)} locations, {len(temperatures)} readings")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing PDF '{filename}': {e}")
            return self._empty_result(error=str(e))
    
    def _extract_text_from_pdf(self, pdf_data: bytes) -> str:
        """Extract text content from PDF bytes"""
        if not PDF_AVAILABLE:
            raise Exception("No PDF processing library available")
        
        text_content = ""
        
        try:
            # Try PyPDF2 first
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            logger.debug(f"PDF has {len(pdf_reader.pages)} pages")
            
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text_content += f"\n--- PAGE {page_num + 1} ---\n"
                text_content += page_text + "\n"
                
        except Exception as e:
            logger.warning(f"PyPDF2 failed: {e}")
            # Try pdfplumber as fallback
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
                    logger.debug(f"PDF has {len(pdf.pages)} pages (pdfplumber)")
                    for page_num, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        text_content += f"\n--- PAGE {page_num + 1} ---\n"
                        text_content += (page_text or "") + "\n"
            except Exception as e2:
                logger.error(f"Both PDF libraries failed: {e2}")
                raise Exception(f"PDF parsing failed: PyPDF2 ({e}), pdfplumber ({e2})")
        
        return text_content
    
    def _extract_locations(self, text_content: str) -> List[Dict]:
        """
        Extract location information from PDF text
        Looks for 'Location Details' sections and extracts the 'Name' field
        """
        locations = []
        lines = text_content.split('\n')
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            
            # Look for 'Location Details' section start
            if line == 'Location Details':
                # Process this location section using the proven logic above
                continue
        
        logger.info(f"Extracted {len(locations)} locations from PDF")
        return locations
    
    def _extract_locations(self, text_content: str) -> List[Dict]:
        """
        Extract location information from PDF text - using proven test parser logic
        """
        locations_found = []
        lines = text_content.split('\n')
        current_location_info = None
        
        for line_num, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            if not line:
                continue
            
            # Look for Location Details sections
            if line == 'Location Details':
                current_location_info = {}
                logger.debug(f"Found 'Location Details' at line {line_num}")
                continue
            
            # Extract location information from structured format
            if current_location_info is not None:
                if line.startswith('Name') and 'name' not in current_location_info:
                    logger.debug(f"Found 'Name' line at {line_num}: '{line}'")
                    
                    # Check if name is on the same line: "Name Dispensary"
                    if len(line) > 4:  # More than just "Name"
                        name_part = line[4:].strip()  # Everything after "Name"
                        if (name_part and 
                            name_part not in ['Description', 'Device', 'Device Model', 'Log Interval', 'View Location'] and
                            not name_part.startswith('S/N:') and 
                            not name_part.startswith('CLT-') and
                            len(name_part) < 50):
                            current_location_info['name'] = name_part
                            logger.debug(f"  ✅ Name from same line: '{name_part}'")
                            continue
                    
                    # If not on same line, look for name in next non-empty line ONLY
                    for next_idx in range(line_num + 1, min(line_num + 3, len(lines))):
                        if next_idx < len(lines):
                            next_line = lines[next_idx].strip()
                            logger.debug(f"  Checking line {next_idx}: '{next_line}'")
                            if (next_line and 
                                next_line not in ['Description', 'Device', 'Device Model', 'Log Interval', 'View Location', 'Temperature'] and
                                not next_line.startswith('S/N:') and 
                                not next_line.startswith('CLT-') and
                                not next_line.startswith('Device S/N:') and
                                len(next_line) < 50):
                                current_location_info['name'] = next_line
                                logger.debug(f"  ✅ Name from next line: '{next_line}'")
                                break
                            elif next_line in ['Description', 'Device', 'Device Model']:
                                logger.debug(f"  ❌ Stopping search at field: '{next_line}'")
                                break
                
                # Extract Description (this will be used to determine final location name)
                elif line.startswith('Description'):
                    # Get description from next line
                    if line_num + 1 < len(lines):
                        desc = lines[line_num + 1].strip()
                        if desc and desc not in ['Device', 'Device Model']:
                            current_location_info['description'] = desc
                            logger.debug(f"  Description: '{desc}'")
                
                elif line.startswith('Device S/N:'):
                    sn_match = re.search(r'Device S/N:\s*(\d+)', line)
                    if sn_match:
                        current_location_info['device_sn'] = sn_match.group(1)
                        logger.debug(f"  Device S/N: {sn_match.group(1)}")
                
                elif 'Alarm Threshold' in line and 'Low Temperature' in ' '.join(lines[max(0, line_num-2):line_num+1]):
                    # Extract low temperature threshold
                    temp_match = re.search(r'(\d+\.?\d*)\s*°C', line)
                    if temp_match:
                        current_location_info['min_temp_threshold'] = float(temp_match.group(1))
                        logger.debug(f"  Min temp: {temp_match.group(1)}°C")
                
                elif 'Alarm Threshold' in line and 'High Temperature' in ' '.join(lines[max(0, line_num-2):line_num+1]):
                    # Extract high temperature threshold  
                    temp_match = re.search(r'(\d+\.?\d*)\s*°C', line)
                    if temp_match:
                        current_location_info['max_temp_threshold'] = float(temp_match.group(1))
                        logger.debug(f"  Max temp: {temp_match.group(1)}°C")
                
                # End of location section - process collected info
                elif line == 'Temperature' and 'name' in current_location_info:
                    # ONLY use the Name field, completely ignore Description
                    location_name = current_location_info['name'].strip()
                    
                    logger.debug(f"✅ LOCATION FOUND: '{location_name}' (using Name only)")
                    
                    location_info = {
                        'name': location_name,
                        'raw_name': location_name,
                        'description': current_location_info.get('description', ''),
                        'device_sn': current_location_info.get('device_sn'),
                        'device_model': current_location_info.get('device_model'),
                        'log_interval': current_location_info.get('log_interval'),
                        'min_temp_threshold': current_location_info.get('min_temp_threshold'),
                        'max_temp_threshold': current_location_info.get('max_temp_threshold')
                    }
                    
                    locations_found.append(location_info)
                    
                    # Reset for next location
                    current_location_info = None
        
        logger.info(f"Extracted {len(locations_found)} locations from PDF")
        return locations_found
    
    def _extract_temperatures(self, text_content: str, locations: List[Dict]) -> List[Dict]:
        """
        Extract temperature readings for each location - using Name field only
        """
        temperatures = []
        lines = text_content.split('\n')
        current_location = None
        in_recordings_section = False
        location_temperatures = {}  # Track all temps per location
        
        for line_num, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            if not line:
                continue
            
            # Look for Location Details sections
            if line.startswith('Location Details'):
                in_recordings_section = False
                current_location = None
                continue
            
            # Extract location name from "Name" field in Location Details
            if line.startswith('Name') and not current_location:
                # Look for the location name (same logic as location extraction)
                location_name = None
                
                # Check if name is on same line
                if len(line) > 4:
                    name_part = line[4:].strip()
                    if (name_part and 
                        name_part not in ['Description', 'Device', 'Device Model'] and
                        len(name_part) < 50):
                        location_name = name_part
                
                # If not on same line, look for name in next line
                if not location_name:
                    for next_line_idx in range(line_num + 1, min(line_num + 3, len(lines))):
                        if next_line_idx < len(lines):
                            next_line = lines[next_line_idx].strip()
                            if (next_line and 
                                next_line not in ['Description', 'Device', 'Device Model', 'Log Interval', 'View Location', 'Temperature'] and
                                not next_line.startswith('S/N:') and 
                                not next_line.startswith('CLT-')):
                                location_name = next_line
                                break
                
                # Use the location name directly (no transformation)
                if location_name:
                    current_location = location_name.strip()
                    location_temperatures[current_location] = {'mins': [], 'maxs': []}
                    logger.debug(f"Processing temperatures for: {current_location}")
                continue
            
            # Look for start of Recordings section
            if line == 'Recordings' and current_location:
                in_recordings_section = True
                logger.debug(f"Found Recordings section for {current_location}")
                continue
            
            # Parse temperature recordings table
            if in_recordings_section and current_location:
                # Look for lines with temperature data: "2025/08/14 05:59PM 4.0°C 4.8°C"
                temp_pattern = r'(\d+\.\d+)°C\s+(\d+\.\d+)°C'
                temp_matches = re.findall(temp_pattern, line)
                
                if temp_matches:
                    logger.debug(f"Found temp data in line {line_num}: {line[:50]}...")
                
                for min_temp_str, max_temp_str in temp_matches:
                    try:
                        min_temp = float(min_temp_str)
                        max_temp = float(max_temp_str)
                        
                        # Skip unrealistic temperatures
                        if min_temp < -50 or min_temp > 100 or max_temp < -50 or max_temp > 100:
                            continue
                        
                        location_temperatures[current_location]['mins'].append(min_temp)
                        location_temperatures[current_location]['maxs'].append(max_temp)
                        
                    except ValueError:
                        continue
            
            # Also check for end of current location section
            if line.startswith('Location Details') and current_location:
                in_recordings_section = False
        
        # Calculate absolute min/max for each location
        for location_name, temp_data in location_temperatures.items():
            if temp_data['mins'] and temp_data['maxs']:
                absolute_min = min(temp_data['mins'])
                absolute_max = max(temp_data['maxs'])
                
                logger.debug(f"{location_name}: {len(temp_data['mins'])} readings, Min {absolute_min}°C, Max {absolute_max}°C")
                
                # Create temperature readings for absolute min and max
                temperatures.extend([
                    {
                        'value': absolute_min,
                        'unit': 'C',
                        'type': 'minimum',
                        'location': location_name,
                        'context': f'Daily minimum from {len(temp_data["mins"])} readings',
                        'timestamp': datetime.now(),
                        'reading_count': len(temp_data['mins'])
                    },
                    {
                        'value': absolute_max,
                        'unit': 'C',
                        'type': 'maximum', 
                        'location': location_name,
                        'context': f'Daily maximum from {len(temp_data["maxs"])} readings',
                        'timestamp': datetime.now(),
                        'reading_count': len(temp_data['maxs'])
                    }
                ])
        
        logger.info(f"Extracted {len(temperatures)} temperature readings")
        return temperatures
    
    def _create_daily_summary(self, temperatures: List[Dict], filename: str) -> Dict:
        """Create a daily summary from temperature readings"""
        if not temperatures:
            return None
        
        # Group by location
        by_location = {}
        for temp in temperatures:
            location = temp['location']
            if location not in by_location:
                by_location[location] = {'mins': [], 'maxs': []}
            
            if temp['type'] == 'minimum':
                by_location[location]['mins'].append(temp['value'])
            elif temp['type'] == 'maximum':
                by_location[location]['maxs'].append(temp['value'])
        
        # Create summary
        summary = {
            'date': datetime.now().date(),
            'source': filename,
            'locations': []
        }
        
        for location, data in by_location.items():
            if data['mins'] and data['maxs']:
                location_summary = {
                    'location': location,
                    'min_temp': min(data['mins']),
                    'max_temp': max(data['maxs']),
                    'readings_count': len(data['mins'])
                }
                summary['locations'].append(location_summary)
        
        return summary if summary['locations'] else None
    
    def _empty_result(self, error: str = None) -> Dict:
        """Return empty result structure"""
        return {
            'locations': [],
            'temperatures': [],
            'daily_summary': None,
            'source': 'unknown',
            'text_length': 0,
            'success': False,
            'error': error
        }
    
    def get_location_names(self, pdf_data: bytes, filename: str = "report.pdf") -> List[str]:
        """Quick method to just get location names from PDF"""
        try:
            result = self.parse_pdf_data(pdf_data, filename)
            return [loc['name'] for loc in result['locations']]
        except Exception as e:
            logger.error(f"Error extracting location names: {e}")
            return []
    
    def validate_pdf_format(self, pdf_data: bytes) -> Tuple[bool, str]:
        """
        Validate if PDF is in expected Clever Logger format
        
        Returns:
            (is_valid, message)
        """
        try:
            text_content = self._extract_text_from_pdf(pdf_data)
            
            # Check for key indicators
            has_location_details = 'Location Details' in text_content
            has_recordings = 'Recordings' in text_content
            has_temp_data = re.search(r'\d+\.?\d*\s*°C', text_content) is not None
            
            if has_location_details and has_recordings and has_temp_data:
                return True, "Valid Clever Logger format detected"
            else:
                missing = []
                if not has_location_details:
                    missing.append("Location Details sections")
                if not has_recordings:
                    missing.append("Recordings sections")
                if not has_temp_data:
                    missing.append("Temperature data")
                
                return False, f"Missing: {', '.join(missing)}"
                
        except Exception as e:
            return False, f"Validation error: {e}"


# Convenience function for standalone use
def parse_pdf_file(file_path: str) -> Dict:
    """
    Parse a PDF file and return temperature data
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Parsed temperature data
    """
    parser = PDFTemperatureParser()
    
    try:
        with open(file_path, 'rb') as file:
            pdf_data = file.read()
        
        filename = file_path.split('/')[-1]  # Get filename from path
        return parser.parse_pdf_data(pdf_data, filename)
        
    except Exception as e:
        logger.error(f"Error reading PDF file '{file_path}': {e}")
        return parser._empty_result(error=str(e))


if __name__ == "__main__":
    # Simple test when run directly
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        result = parse_pdf_file(pdf_path)
        
        print(f"\n📊 PDF Parsing Results:")
        print(f"✅ Success: {result['success']}")
        print(f"📍 Locations: {len(result['locations'])}")
        
        for loc in result['locations']:
            print(f"  • {loc['name']}")
        
        print(f"🌡️ Temperature readings: {len(result['temperatures'])}")
        for temp in result['temperatures']:
            print(f"  • {temp['location']}: {temp['value']}°C ({temp['type']})")
    else:
        print("Usage: python pdf_parser.py <pdf_file_path>")

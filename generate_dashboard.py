#!/usr/bin/env python3
"""
Local dashboard generator for development
Usage: python generate_dashboard.py [--sample]
"""

import json
import os
import sys
from datetime import datetime, timedelta
import argparse

def generate_sample_data():
    """Generate sample data for development"""
    start_date = datetime.now().date()
    sample_sites = []
    
    # Sample data for different areas
    areas = [
        ("Mount Tamalpais SP", "S Rav Cabin Area", 766),
        ("Mount Tamalpais SP", "S Rav Camp Area (sites E1-E7)", 590),
        ("Mount Tamalpais SP", "Frank Valley Horse Camp", 589),
        ("Point Reyes National Seashore", "Point Reyes National Seashore Campground", 233359),
        ("Julia Pfeiffer Burns SP", "Environmental Group Camp Area", 518),
    ]
    
    for i, (rec_area, facility, campground_id) in enumerate(areas):
        for j in range(5):  # 5 dates per facility
            date = start_date + timedelta(days=i*7 + j*2)
            sample_sites.append({
                'campsite_id': f'site_{i}_{j}',
                'booking_date': date.isoformat(),
                'campsite_site_name': f'Site {j+1}',
                'facility_name': facility,
                'booking_url': f'https://example.com/book/{i}_{j}',
                'recreation_area': rec_area,
                'campsite_type': 'STANDARD',
                'campground_id': campground_id,
                'num_nights': 1
            })
    
    return sample_sites

def generate_dashboard(sites_data, output_path='dashboard/index.html'):
    """Generate the dashboard HTML file"""
    
    # Read template
    template_path = 'dashboard/template.html'
    if not os.path.exists(template_path):
        print(f"Error: Template not found at {template_path}")
        return False
    
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Group sites by recreation area for stats
    areas = set(site['recreation_area'] for site in sites_data)
    
    # Generate email content preview (simplified version)
    sites_by_area = {}
    for site in sites_data:
        area = site['recreation_area']
        facility = site['facility_name']
        if area not in sites_by_area:
            sites_by_area[area] = {}
        if facility not in sites_by_area[area]:
            sites_by_area[area][facility] = []
        sites_by_area[area][facility].append(site)
    
    email_content = f"""
        <h1>🏕️ Campsite Availability Alert</h1>
        <div class="summary">
            <strong>Found {len(sites_data)} available campsites across {len(areas)} areas</strong>
        </div>
    """
    
    # Sort areas to put Steep Ravine first
    sorted_areas = sorted(sites_by_area.items(), key=lambda x: (
        not any(site.get('campground_id') in [766, 590] for sites in x[1].values() for site in sites),
        x[0]
    ))
    
    for area, facilities in sorted_areas:
        email_content += f'<h1 class="rec-area-header">🏞️ {area}</h1>'
        
        for facility, sites in facilities.items():
            email_content += f'<h2>{facility}</h2>'
            email_content += '''
                <table>
                    <thead>
                        <tr>
                            <th>Available Date</th>
                            <th>Nights</th>
                            <th>Book Now</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            # Sort sites by date
            sites.sort(key=lambda x: x['booking_date'])
            for site in sites[:5]:  # Limit to 5 for preview
                nights = site.get('num_nights', 1)
                email_content += f'''
                    <tr>
                        <td>{site['booking_date']}</td>
                        <td>{nights} night{"s" if nights != 1 else ""}</td>
                        <td><a href="{site['booking_url']}" class="book-link">Book Now</a></td>
                    </tr>
                '''
            
            email_content += '''
                    </tbody>
                </table>
            '''
    
    # Replace template variables
    html_content = template.replace('{{LAST_UPDATED}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    html_content = html_content.replace('{{TOTAL_SITES}}', str(len(sites_data)))
    html_content = html_content.replace('{{TOTAL_AREAS}}', str(len(areas)))
    html_content = html_content.replace('{{EMAIL_CONTENT}}', email_content)
    html_content = html_content.replace('{{SITES_DATA}}', json.dumps(sites_data, indent=2))
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write output file
    with open(output_path, 'w') as f:
        f.write(html_content)
    
    print(f"Dashboard generated: {output_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Generate Camply Dashboard')
    parser.add_argument('--sample', action='store_true', help='Generate with sample data')
    parser.add_argument('--input', help='JSON file with sites data')
    parser.add_argument('--output', default='dashboard/index.html', help='Output HTML file')
    
    args = parser.parse_args()
    
    if args.sample:
        sites_data = generate_sample_data()
        print(f"Generated {len(sites_data)} sample sites")
    elif args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            return 1
        with open(args.input, 'r') as f:
            sites_data = json.load(f)
    else:
        print("Error: Either --sample or --input is required")
        return 1
    
    if generate_dashboard(sites_data, args.output):
        print(f"Open {args.output} in your browser to view the dashboard")
        return 0
    else:
        return 1

if __name__ == '__main__':
    sys.exit(main())

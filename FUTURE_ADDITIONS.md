# Camply Checker - Future Additions List

## 🎯 **Potential Additions to Monitor**

### 🏔️ **Wilderness Permits**
- **Desolation Wilderness (233261)** - Lake Tahoe area
  - 45 zones, quota system Memorial Day - Sept 30
  - Cancellations make permits available again
  - High value: Popular zones book out in minutes
  - Would need different monitoring logic (permits vs campsites)

### 🏕️ **Car Camping Campgrounds**

#### Recreation.gov Options:
- **Upper Pines Campground (232447)** - Yosemite Valley
- **Kirk Creek Campground (233116)** - Big Sur coastal camping  
- **Headquarters (232819)** - Sequoia National Forest

#### ReserveCalifornia Options:
- **Angel Island State Park** - San Francisco Bay island camping
  - 10 environmental campsites (hike-in from ferry)
  - Unique island experience, accessible by ferry only
  - Books 6 months in advance on ReserveCalifornia.com
  - ❌ **Extensive Research Result**: Not accessible through camply library
    - Tested 50+ park IDs and recreation_area parameters
    - ReserveCalifornia integration in camply appears limited
    - May only work with specific parks that camply has mapped
    - **Alternative approaches**:
      - Use CampNab or similar third-party alert services
      - Manual monitoring at 8am when new dates open (6 months ahead)
      - Direct ReserveCalifornia API integration (would require custom code)
  
### 🚫 **Not Compatible with Current System**
- **Anthony Chabot Regional Park** - Lake Chabot area
  - 75 campsites including 10 hike-in tent sites
  - East Bay Regional Parks system (ReserveAmerica.com)
  - Different reservation system, not compatible

- **Angel Island State Park** - San Francisco Bay island
  - 10 environmental campsites, ferry access only
  - ReserveCalifornia system but difficult to integrate with camply
  - Requires specific recreation_area parameters not easily discoverable
  - Recommendation: Use CampNab or similar third-party alert services

### 🔍 **Search Improvements**
- **Point Reyes filter is correct** ✅
  - Currently captures: "HIKE TO" (454 sites) + "GROUP HIKE TO" (123 sites)
  - Correctly excludes: "BOAT IN" (60 sites) + boat group sites (90 sites)
  - No tent-only sites being missed - all hike-in sites are captured

#### Other Areas Previously Discovered:
- **Upper Paradise Lake Cabin (233000)** - Chugach National Forest, AK
  - 14 cabin sites available, but in Alaska (probably not relevant)
- **Toad Suck (232721)** - Arkansas River, AR  
  - 374 sites but in Arkansas (not California)
- **Little Shaheen Cabin (232923)** - Tongass National Forest, AK
  - 14 cabin sites in Alaska (not relevant)

### 📧 **Email Enhancements**
- Add weather alerts for camping dates
- Include driving directions to campgrounds
- Show campground amenities (showers, water, etc.)

### 🎛️ **System Features**
- Web dashboard to manage campgrounds
- SMS notifications in addition to email
- Different notification schedules (immediate vs daily digest)
- Campground-specific search windows (some open earlier than others)

---

## 🔧 **Current Configuration**
- **ReserveCalifornia**: 6 campgrounds (Mount Tamalpais, Julia Pfeiffer Burns)
- **Recreation.gov**: 2 campgrounds (Sardine Peak Lookout, Point Reyes hike-in only)
- **Email**: Deduplication enabled, BCC recipients, formatted tables
- **Schedule**: Every 30 minutes
- **Search window**: 90 days

---

## 📝 **Notes**
- Point Reyes filter may be too restrictive (only "HIKE TO" sites)
- Need to research what other tent/hike sites we might be missing
- Wilderness permits would require different monitoring approach
- Consider priority order for additions based on value/effort

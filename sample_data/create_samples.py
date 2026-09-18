import os
try:
    # pyrefly: ignore [missing-import]
    import pymupdf as fitz
except ImportError:
    import fitz

os.makedirs("sample_data", exist_ok=True)

# 1. FIR-001: Multi-page PDF (Page 1: General Info & Rahul Menon; Page 2: Specific vehicle & phone evidence)
doc1 = fitz.open()

# Page 1
page1 = doc1.new_page(width=595, height=842)
text_p1 = """FIRST INFORMATION REPORT
(Under Section 154 Cr.P.C.)
State: Kerala | District: Kozhikode | Police Station: Town PS
FIR No: 0142/2026 | Date: 12-01-2026
1. Complainant / Informant: Inspector K. Vijayan
2. Details of Suspect:
Name: Rahul Menon
Age: 32 Years
Address: Flat 4B, Emerald Heights, Kozhikode
Status: Under Surveillance / Person of Interest

3. Incident Overview:
During routine highway surveillance near NH-66 on 11-01-2026, the suspect Rahul Menon
was observed coordinating suspicious cargo offloading. Surveillance teams noted frequent
encrypted mobile communications."""
page1.insert_text((50, 70), text_p1, fontsize=11)

# Page 2
page2 = doc1.new_page(width=595, height=842)
text_p2 = """FIR No: 0142/2026 - PAGE 2 CONTINUED

4. Evidence & Communication Details:
Rahul Menon was actively using mobile number 9876543210 to coordinate logistics.
Calls were tracked connecting repeatedly to local handlers in the Kozhikode market.

5. Vehicle Details:
The suspect was observed driving a dark grey sedan with registration number KL-11-AB-1234.
The vehicle was seen parked at Mavoor Road prior to departure toward the highway.

Investigating Officer: Sub-Inspector M. Thomas
Badge No: KL-4092"""
page2.insert_text((50, 70), text_p2, fontsize=11)

doc1.save("sample_data/FIR-001.pdf")
doc1.close()
print("Generated sample_data/FIR-001.pdf (2 pages)")

# 2. FIR-002: Single-page PDF with Arjun Das sharing the same phone and vehicle
doc2 = fitz.open()
page = doc2.new_page(width=595, height=842)
text_p = """FIRST INFORMATION REPORT
(Under Section 154 Cr.P.C.)
State: Kerala | District: Kozhikode | Police Station: Medical College PS
FIR No: 0198/2026 | Date: 18-01-2026

1. Complainant: SI Rajesh Kumar
2. Suspect Details:
Name: Arjun Das
Alias: Dasan
Address: Beach Road, Calicut

3. Investigation Narrative:
During an inquiry into an unauthorized fuel depot, suspect Arjun Das was intercepted.
Investigating officers found Arjun Das using contact number 9876543210.
Furthermore, vehicle registration KL-11-AB-1234 was registered as associated transport
used by Arjun Das for local distribution.

Investigating Officer: SI Rajesh Kumar
Station: Medical College PS, Kozhikode"""
page.insert_text((50, 70), text_p, fontsize=11)

doc2.save("sample_data/FIR-002.pdf")
doc2.close()
print("Generated sample_data/FIR-002.pdf (1 page)")

# 3. Invalid non-PDF file
with open("sample_data/invalid_sample.txt", "w", encoding="utf-8") as f:
    f.write("This is a plain text file, not a PDF document.")
print("Generated sample_data/invalid_sample.txt")

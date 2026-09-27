from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

pdf_path = "scratch/fixture_matrix.pdf"
doc = SimpleDocTemplate(pdf_path, pagesize=letter)

data = [
    ["Variant", "Max Power", "ABS", "Boot Space"],
    ["Base Petrol MT", "50 kW", "\uf0fc", "300 L"],
    ["Mid Petrol AMT", "50 kW", "\uf0fc", "300 L"],
    ["Base CNG MT", "40 kW", "-", "200 L"]
]

table = Table(data)
style = TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.grey),
    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('BOTTOMPADDING', (0,0), (-1,0), 12),
    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
    ('GRID', (0,0), (-1,-1), 1, colors.black)
])
table.setStyle(style)

doc.build([table])
print(f"Fixture PDF created at {pdf_path}")

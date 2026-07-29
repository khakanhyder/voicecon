import re

files = [
    "frontend/src/app/dashboard/settings/api-keys/page.tsx",
    "frontend/src/app/dashboard/settings/profile/page.tsx",
    "frontend/src/app/dashboard/settings/team/page.tsx"
]

input_class = 'className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 text-[14px]"'
textarea_class = 'className="w-full rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 py-2 text-[14px]"'

for path in files:
    with open(path, "r") as f:
        content = f.read()

    # 1. Update Card borders
    content = re.sub(r'rounded-lg border bg-card p-6', r'rounded-[10px] border border-[#000000] bg-white p-6', content)
    
    # Alerts/Notices Custom Borders
    content = re.sub(r'rounded-lg border border-primary bg-primary/5 p-6', r'rounded-[10px] border border-[#000000] bg-[#0F6A590A] p-6', content)
    content = re.sub(r'rounded-lg border-2 border-destructive/20 bg-destructive/5 p-6', r'rounded-[10px] border border-[#000000] bg-[#0F6A590A] p-6', content)
    
    # Sub-item boxes (e.g., individual Team Members or API Key rows)
    content = re.sub(r'rounded-lg border p-4', r'rounded-[10px] border border-[#000000] p-4 bg-white', content)
    content = re.sub(r'rounded-lg border border-dashed p-4', r'rounded-[10px] border border-dashed border-[#000000] p-4 bg-white', content)

    # 2. Update Input elements
    def replace_input(m):
        attr = m.group(1)
        if 'className=' in attr:
            # Replace existing className
            attr2 = re.sub(r'className="[^"]*"', input_class, attr)
            return f'<Input{attr2}/>'
        else:
            return f'<Input{attr} {input_class} />'
            
    content = re.sub(r'<Input([^>]*?)\s*/>', replace_input, content, flags=re.DOTALL)
    
    # 3. Update Textarea elements
    def replace_textarea(m):
        attr = m.group(1)
        if 'className=' in attr:
            attr2 = re.sub(r'className="[^"]*"', textarea_class, attr)
            return f'<Textarea{attr2}/>'
        else:
            return f'<Textarea{attr} {textarea_class} />'
            
    content = re.sub(r'<Textarea([^>]*?)\s*/>', replace_textarea, content, flags=re.DOTALL)

    # 4. Handle standard Labels
    content = re.sub(r'<Label htmlFor="([^"]+)">', r'<Label htmlFor="\1" className="text-[14px] font-bold text-[#000000] font-poppins block">', content)
    content = re.sub(r'<Label>', r'<Label className="text-[14px] font-bold text-[#000000] font-poppins block">', content)
    
    # 5. Handle Select drops that are raw <select> elements
    content = re.sub(r'(<select[^>]*?)\s+className="[^"]*"', rf'\1 {input_class}', content, flags=re.DOTALL)

    with open(path, "w") as f:
        f.write(content)

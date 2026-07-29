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

    def replace_input(m):
        attr = m.group(1)
        # Avoid modifying elements that are already fully processed (if any, though it's idempotent for styling)
        if 'className=' in attr:
            attr2 = re.sub(r'className="[^"]*"', input_class, attr)
            return f'<Input{attr2}/>'
        else:
            return f'<Input{attr} {input_class} />'
            
    content = re.sub(r'<Input\b(.*?)/>', replace_input, content, flags=re.DOTALL)
    
    def replace_textarea(m):
        attr = m.group(1)
        if 'className=' in attr:
            attr2 = re.sub(r'className="[^"]*"', textarea_class, attr)
            return f'<Textarea{attr2}/>'
        else:
            return f'<Textarea{attr} {textarea_class} />'
            
    content = re.sub(r'<Textarea\b(.*?)/>', replace_textarea, content, flags=re.DOTALL)

    with open(path, "w") as f:
        f.write(content)

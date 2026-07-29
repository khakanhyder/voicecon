import re

path = "frontend/src/app/dashboard/knowledge/[id]/page.tsx"
with open(path, "r") as f:
    orig = f.read()

# 1. Add download handler and meta helper

handler_code = """
  const handleDownload = async (docId: string, title: string) => {
    try {
      const url = API_ENDPOINTS.KNOWLEDGE_DOCUMENT_DOWNLOAD(docId);
      const token = localStorage.getItem('token');
      const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      const dlName = title.toLowerCase().endswith('.txt') ? title : `${title}.txt`;
      a.download = title; 
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      toast.error('Failed to download document');
    }
  }

  const getFileMeta = (title: string, mime?: string | null) => {
    const ext = title.split('.').pop()?.toLowerCase() || '';
    if (['pdf'].includes(ext) || (mime && mime.includes('pdf'))) {
      return { label: 'PDF', bg: 'bg-red-500', name: 'PDF Document' };
    } else if (['doc', 'docx'].includes(ext) || (mime && mime.includes('word'))) {
      return { label: 'DOC', bg: 'bg-blue-500', name: 'Word Document' };
    } else if (['xls', 'xlsx'].includes(ext) || (mime && (mime.includes('excel') || mime.includes('spreadsheet')))) {
      return { label: 'XLS', bg: 'bg-green-500', name: 'Excel Spreadsheet' };
    } else if (['csv'].includes(ext)) {
      return { label: 'CSV', bg: 'bg-green-500', name: 'CSV File' };
    } else if (['ppt', 'pptx'].includes(ext) || (mime && mime.includes('powerpoint'))) {
      return { label: 'PPT', bg: 'bg-orange-500', name: 'PowerPoint' };
    } else if (['txt', 'md', 'json'].includes(ext)) {
      return { label: ext.toUpperCase(), bg: 'bg-slate-500', name: 'Text Document' };
    }
    return { label: ext ? ext.substring(0,3).toUpperCase() : 'DOC', bg: 'bg-slate-500', name: mime || 'Document' };
  }

  const handleDeleteDoc = async (doc: KBDocument) => {
"""

# Replace `const handleDeleteDoc = ...` to prepend code
res = orig.replace('  const handleDeleteDoc = async (doc: KBDocument) => {', handler_code)

# 2. Update the rendering of the document
# From:
# <div className="flex items-center justify-center h-10 w-10 bg-blue-500 rounded text-white shrink-0 font-bold text-xs uppercase">
#   {d.title.split('.').pop()?.slice(0, 3) || 'PDF'}
# </div>
# <div className="min-w-0">
#   <p className="text-[18px] font-poppins text-[#000000] truncate">{d.title}</p>
#   <p className="text-[12px] font-poppins text-black mt-0.5">
#     application/pdf • {d.file_size ? `${(d.file_size / 1024).toFixed(2)} KB` : 'Unknown size'}
#   </p>

# And:
# <Button className="bg-[#106959] hover:opacity-90 text-white rounded-[8px] font-poppins font-medium h-[40px] px-6">
#   Download
# </Button>

render_orig = """<div className="flex items-center justify-center h-10 w-10 bg-blue-500 rounded text-white shrink-0 font-bold text-xs uppercase">
                    {d.title.split('.').pop()?.slice(0, 3) || 'PDF'}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[18px] font-poppins text-[#000000] truncate">{d.title}</p>
                    <p className="text-[12px] font-poppins text-black mt-0.5">
                      application/pdf • {d.file_size ? `${(d.file_size / 1024).toFixed(2)} KB` : 'Unknown size'}
                    </p>"""
                    
render_repl = """{
                    (() => {
                      const meta = getFileMeta(d.title, d.file_type);
                      return (
                        <>
                          <div className={`flex items-center justify-center h-10 w-10 ${meta.bg} rounded text-white shrink-0 font-bold text-xs uppercase`}>
                            {meta.label}
                          </div>
                          <div className="min-w-0">
                            <p className="text-[18px] font-poppins text-[#000000] truncate">{d.title}</p>
                            <p className="text-[12px] font-poppins text-black mt-0.5">
                              {meta.name} • {d.file_size ? `${(d.file_size / 1024).toFixed(2)} KB` : 'Unknown size'}
                            </p>
                        </>
                      );
                    })()}"""


res = res.replace(render_orig, render_repl)

# Update the Download button
btn_orig = """<Button className="bg-[#106959] hover:opacity-90 text-white rounded-[8px] font-poppins font-medium h-[40px] px-6">
                    Download
                  </Button>"""

btn_repl = """<Button onClick={() => handleDownload(d.id, d.title)} className="bg-[#106959] hover:opacity-90 text-white rounded-[8px] font-poppins font-medium h-[40px] px-6">
                    Download
                  </Button>"""

res = res.replace(btn_orig, btn_repl)

with open(path, "w") as f:
    f.write(res)


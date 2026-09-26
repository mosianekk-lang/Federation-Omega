from __future__ import annotations
import json,threading,tkinter as tk
from tkinter import ttk
from . import __version__
from .catalog import OFFERINGS,RESTRICTED_CAPABILITIES
from .runtime import heartbeat,signed_update_state,status
def _pretty(obj): return json.dumps(obj,indent=2,sort_keys=True,default=str)
class FuseTokaApp(tk.Tk):
    def __init__(self): super().__init__(); self.title(f"FUSE Toka {__version__}"); self.geometry("1100x720"); self.minsize(900,620); self._build()
    def _build(self):
        h=ttk.Frame(self,padding=12); h.pack(fill=tk.X); ttk.Label(h,text="FUSE Toka",font=("Segoe UI",22,"bold")).pack(side=tk.LEFT); ttk.Label(h,text=f"v{__version__} • sovereign intelligence & investigations platform").pack(side=tk.LEFT,padx=14)
        n=ttk.Notebook(self); n.pack(fill=tk.BOTH,expand=True,padx=10,pady=(0,10)); c=ttk.Frame(n,padding=10); o=ttk.Frame(n,padding=10); p=ttk.Frame(n,padding=10); n.add(c,text="Commercial Offering"); n.add(o,text="LiveCare / Update"); n.add(p,text="Governed Boundaries")
        t=ttk.Treeview(c,columns=("summary","benchmark"),show="headings"); t.heading("summary",text="Capability"); t.heading("benchmark",text="Benchmark DNA"); t.column("summary",width=590,anchor=tk.W); t.column("benchmark",width=390,anchor=tk.W)
        for item in OFFERINGS: t.insert("",tk.END,values=(f"{item['name']} — {item['summary']}",item["benchmark"]))
        t.pack(fill=tk.BOTH,expand=True)
        b=ttk.Frame(o); b.pack(fill=tk.X); self.out=tk.Text(o,wrap=tk.WORD,height=28); self.out.pack(fill=tk.BOTH,expand=True,pady=(10,0)); ttk.Button(b,text="Runtime Status",command=lambda:self._show(status().__dict__)).pack(side=tk.LEFT,padx=(0,8)); ttk.Button(b,text="Connect / Heartbeat",command=lambda:self._async(heartbeat)).pack(side=tk.LEFT,padx=(0,8)); ttk.Button(b,text="Check Signed Update",command=lambda:self._async(signed_update_state)).pack(side=tk.LEFT); self._show(status().__dict__)
        x=tk.Text(p,wrap=tk.WORD); x.pack(fill=tk.BOTH,expand=True); x.insert(tk.END,"FUSE Toka packages lawful intelligence, investigations, defensive cyber, site protection and evidence workflows.\n\n"); [x.insert(tk.END,f"• {k}: {v}\n") for k,v in RESTRICTED_CAPABILITIES.items()]; x.configure(state=tk.DISABLED)
    def _show(self,obj): self.out.delete("1.0",tk.END); self.out.insert(tk.END,_pretty(obj))
    def _async(self,fn):
        def run():
            r=fn(); self.after(0,lambda:self._show(r))
        threading.Thread(target=run,daemon=True).start()
def main(): FuseTokaApp().mainloop()
if __name__=="__main__": main()

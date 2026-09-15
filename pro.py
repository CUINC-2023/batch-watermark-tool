"""Visual editor and safe batch orchestration for v4.2."""
import copy
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageOps
import app as base
from enhancements import EnhancedApp
from imaging import Processor, validate_profile, safe_name, crop_box, encode_image, atomic_write

VERSION = '4.2'
LOG = logging.getLogger('watermark')


def setup_logging():
    base.APP_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG.handlers:
        handler = RotatingFileHandler(base.APP_DIR/'errors.log',maxBytes=2_000_000,backupCount=3,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        LOG.addHandler(handler)
        LOG.setLevel(logging.INFO)


class ProApp(EnhancedApp):
    def __init__(self):
        self._ready = False
        self._preview_job = None
        self._crops = {}
        self._thumbs = {}
        self._gesture = None
        self._handles = {}
        self._busy = False
        self._pending_pro = {}
        self._events = queue.Queue()
        self._stop = threading.Event()
        setup_logging()
        super().__init__()
        self.max_kb = tk.DoubleVar(self, self._pending_pro.get('max_kb',0))
        self.edit_mode = tk.StringVar(self,'預覽')
        self.title(f'Batch Watermark Tool Pro v{VERSION}')
        self.minsize(min(960,self.winfo_screenwidth()-40),600)
        self.geometry(f'{min(1540,self.winfo_screenwidth()-40)}x{min(940,self.winfo_screenheight()-120)}')
        toolbar = ttk.Frame(self.canvas.master)
        toolbar.pack(fill='x',before=self.canvas)
        for mode in ('預覽','裁切框','Logo'):
            ttk.Radiobutton(toolbar,text=mode,value=mode,variable=self.edit_mode,command=self.preview).pack(side='left',padx=4)
        ttk.Button(toolbar,text='重設此圖裁切',command=self.reset_crop).pack(side='left',padx=4)
        ttk.Button(toolbar,text='錯誤日誌',command=self.show_logs).pack(side='right')
        self.canvas.bind('<Button-1>',self.pointer_down)
        self.canvas.bind('<B1-Motion>',self.pointer_move)
        self.canvas.bind('<ButtonRelease-1>',self.pointer_up)
        self.canvas.bind('<Escape>',lambda e:self.pointer_up(e))
        self.tree.bind('<Delete>',lambda e:self.remove_selected())
        self.unbind('<Delete>')
        ttk.Style(self).configure('Treeview',rowheight=60)
        self._upgrade_widgets(self)
        self._compact_layout()
        self._scroll_settings(self)
        self._ready = True
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(100,self.poll_events)
        self.preview()

    def _compact_layout(self):
        # Reserve footer controls before the expanding body on every screen size.
        top,body,bottom,source = self.winfo_children()[:4]
        bottom.pack_configure(side='bottom',before=body)
        source.pack_configure(side='bottom',before=body)
        labels=[w for w in bottom.winfo_children() if isinstance(w,ttk.Label)]
        for w in labels: w.pack_forget()
        for w in labels: w.pack(fill='x',side='top',before=self.progress)
        self.progress.configure(length=120)
        if self.winfo_screenwidth() <= 1280:
            self.tree.column('#0',width=140,minwidth=100)
            self.tree.column('size',width=70,minwidth=60)
            self.tree.master.master.winfo_children()[-1].configure(wraplength=220)
            ttk.Style(self).configure('TButton',padding=(5,4))
            # Put the title on its own line; all import/quick actions remain reachable.
            for w in top.winfo_children():
                if isinstance(w,ttk.Label):
                    w.pack_forget()
            heading=ttk.Label(top,text='Batch Watermark Tool Pro v'+VERSION,style='Title.TLabel')
            heading.pack(side='top',anchor='w',before=top.winfo_children()[2])
            # Preview controls are spread over two rows instead of being clipped.
            center=self.canvas.master.master
            preview_bar=center.winfo_children()[0]
            for w in preview_bar.winfo_children():
                if isinstance(w,ttk.Checkbutton):
                    w.pack_forget();w.pack(side='bottom',anchor='w')
                elif isinstance(w,ttk.Button) and w.cget('text') in ('＋','－'):
                    w.pack_forget()
            edit_bar=self.canvas.master.winfo_children()[-1]
            for w in edit_bar.winfo_children():
                if isinstance(w,ttk.Button):
                    w.pack_forget();w.pack(side='bottom',fill='x')
            for w in source.winfo_children():
                if isinstance(w,ttk.Label) and w.cget('text').startswith('例：'):w.pack_forget()

    def _scroll_settings(self,parent):
        for child in parent.winfo_children():
            if isinstance(child,ttk.Notebook):
                pages=[(child.nametowidget(tab),child.tab(tab,'text')) for tab in child.tabs()]
                for page,title in pages:
                    child.forget(page)
                    holder=ttk.Frame(child)
                    canvas=tk.Canvas(holder,highlightthickness=0,bg='#171a1d',width=350)
                    scrollbar=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview)
                    canvas.configure(yscrollcommand=scrollbar.set)
                    scrollbar.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
                    item=canvas.create_window(0,0,anchor='nw',window=page)
                    page.bind('<Configure>',lambda e,c=canvas:c.configure(scrollregion=c.bbox('all')))
                    canvas.bind('<Configure>',lambda e,c=canvas,i=item:c.itemconfigure(i,width=e.width))
                    child.add(holder,text=title)
            else:
                self._scroll_settings(child)

    def _upgrade_widgets(self,w):
        for child in w.winfo_children():
            if isinstance(child,ttk.Combobox) and tuple(child.cget('values')) == ('JPG','JPEG','PNG'):
                child.configure(values=('JPG','JPEG','PNG','WEBP'))
                row = ttk.Frame(child.master)
                row.pack(fill='x',after=child,pady=5)
                ttk.Label(row,text='檔案上限 KB（0 不限）').pack(side='left')
                ttk.Entry(row,textvariable=self.max_kb,width=9).pack(side='right')
            if isinstance(child,ttk.Label):
                if child.cget('text') == 'v4': child.configure(text='v'+VERSION)
                if child.cget('text') == 'JPG 品質': child.configure(text='JPG / WebP 品質')
                if child.cget('text').startswith('自由位置：'):
                    child.configure(text='裁切框：拖曳移動／四角縮放　Logo：四角縮放／圓點旋轉')
            self._upgrade_widgets(child)

    def report_callback_exception(self,exc,val,tb):
        LOG.error('UI callback failed',exc_info=(exc,val,tb))
        messagebox.showerror('操作失敗',f'{val}\n詳細資訊已寫入錯誤日誌',parent=self)

    def show_logs(self):
        win = tk.Toplevel(self)
        win.title('錯誤日誌')
        win.geometry('850x480')
        text = tk.Text(win,wrap='word')
        text.pack(fill='both',expand=True)
        p = base.APP_DIR/'errors.log'
        text.insert('1.0',p.read_text(encoding='utf-8')[-100000:] if p.exists() else '尚無錯誤')
        text.configure(state='disabled')
        ttk.Label(win,text=str(p)).pack(fill='x')

    def config(self):
        c = super().config()
        c['max_kb'] = self.max_kb.get() if self._ready else self._pending_pro.get('max_kb',0)
        return c

    def apply_cfg(self,c):
        self._pending_pro = dict(c)
        super().apply_cfg(c)
        if self._ready: self.max_kb.set(c.get('max_kb',0))

    def _on_live_change(self,*_):
        self.preview()

    def preview(self):
        if not self._ready: return
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(70,self.render_preview)

    def current_path(self):
        selection = self.tree.selection()
        return self.paths[int(selection[0])] if selection else (self.paths[0] if self.paths else None)

    def single_profile(self):
        return validate_profile(dict(ratio=self.output_ratio.get(),mode=self.size_mode.get(),pct=self.resize_percent.get(),edge=self.long_edge.get(),format=self.output_format.get(),quality=self.quality.get(),max_kb=self.max_kb.get()))

    def render_preview(self):
        self._preview_job = None
        self.canvas.delete('all')
        self._handles = {}
        self.preview_box = None
        path = self.current_path()
        if not path: return
        try:
            mode = self.edit_mode.get()
            if mode == '裁切框':
                with Image.open(path) as im: img = ImageOps.exif_transpose(im).convert('RGBA')
            else:
                img,_ = Processor(self.config(),self._crops).process_profile(path,self.single_profile(),self.preview_processed.get())
            self._image_size = img.size
            cw,ch = max(1,self.canvas.winfo_width()-24),max(1,self.canvas.winfo_height()-45)
            scale = min(cw/img.width,ch/img.height)*self.preview_zoom.get()
            p = img.resize((max(1,round(img.width*scale)),max(1,round(img.height*scale))),Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(p)
            l,t = (self.canvas.winfo_width()-p.width)/2,(self.canvas.winfo_height()-p.height)/2
            self.preview_box = (l,t,l+p.width,t+p.height)
            self.canvas.create_image(l,t,anchor='nw',image=self.preview_photo)
            self._view_scale = (p.width/img.width,p.height/img.height)
            self.canvas.create_text(10,10,anchor='nw',text=f'{img.width} × {img.height}px · 單張輸出設定預覽',fill='white')
            if mode == '裁切框': self.draw_crop(path)
            elif mode == 'Logo' and self.preview_processed.get() and self.watermark_path and self.wm_enabled.get() and self.wm_mode.get() != '平鋪': self.draw_logo()
            self._refresh_enhanced_summary()
        except (ValueError,tk.TclError) as e:
            self.status.set(f'請檢查設定：{e}')
        except Exception:
            LOG.exception('Preview failed: %s',path)
            self.status.set('預覽失敗，請查看錯誤日誌')

    def screen_point(self,x,y):
        l,t,_,_ = self.preview_box
        sx,sy = self._view_scale
        return l+x*sx,t+y*sy

    def image_point(self,e):
        l,t,_,_ = self.preview_box
        sx,sy = self._view_scale
        return (e.x-l)/sx,(e.y-t)/sy

    def handle(self,name,x,y,round_handle=False):
        self._handles[name]=(x,y)
        fn = self.canvas.create_oval if round_handle else self.canvas.create_rectangle
        fn(x-6,y-6,x+6,y+6,fill='#5aa7ff',outline='white')

    def draw_crop(self,path):
        cx,cy,z = self._crops.get(path,(self.crop_x.get(),self.crop_y.get(),1))
        box = crop_box(self._image_size,base.RATIOS[self.output_ratio.get()],cx,cy,z)
        self._crop_box = box
        l,t = self.screen_point(*box[:2]); r,b = self.screen_point(*box[2:])
        il,it,ir,ib = self.preview_box
        for rect in ((il,it,ir,t),(il,b,ir,ib),(il,t,l,b),(r,t,ir,b)):
            self.canvas.create_rectangle(*rect,fill='black',stipple='gray50',outline='')
        self.canvas.create_rectangle(l,t,r,b,outline='white',width=2)
        for f in (1/3,2/3):
            self.canvas.create_line(l+(r-l)*f,t,l+(r-l)*f,b,fill='#bbbbbb',dash=(3,3))
            self.canvas.create_line(l,t+(b-t)*f,r,t+(b-t)*f,fill='#bbbbbb',dash=(3,3))
        for name,x,y in [('nw',l,t),('ne',r,t),('se',r,b),('sw',l,b)]: self.handle(name,x,y)

    def draw_logo(self):
        w,h = self._image_size
        with Image.open(self.watermark_path) as im:
            lw = max(1,int(w*self.wm_scale.get()/100))
            lh = max(1,int(im.height*lw/im.width))
        a = math.radians(self.wm_rotation.get())
        rw,rh = abs(lw*math.cos(a))+abs(lh*math.sin(a)),abs(lw*math.sin(a))+abs(lh*math.cos(a))
        if self.wm_mode.get() == '自由位置': cx,cy=self.free_x.get()*w,self.free_y.get()*h
        else:
            x,y = self.anchor((w,h),(rw,rh),self.wm_position.get(),self.margin.get())
            cx,cy=x+rw/2,y+rh/2
        self._logo_center=(cx,cy)
        points=[]
        for name,x,y in [('nw',-lw/2,-lh/2),('ne',lw/2,-lh/2),('se',lw/2,lh/2),('sw',-lw/2,lh/2)]:
            px,py=self.screen_point(cx+x*math.cos(a)+y*math.sin(a),cy-x*math.sin(a)+y*math.cos(a))
            points.extend((px,py)); self.handle(name,px,py)
        self.canvas.create_polygon(*points,fill='',outline='#5aa7ff',width=2)
        px,py=self.screen_point(cx-lh/2*math.sin(a),cy-lh/2*math.cos(a))
        rx,ry=px-30*math.sin(a),py-30*math.cos(a)
        self.canvas.create_line(px,py,rx,ry,fill='white')
        self.handle('rotate',rx,ry,True)

    def pointer_down(self,e):
        if not self.preview_box or self.edit_mode.get() == '預覽': return
        self.canvas.focus_set()
        hit = next((n for n,(x,y) in self._handles.items() if math.hypot(e.x-x,e.y-y)<=12),None)
        x,y=self.image_point(e)
        if self.edit_mode.get() == '裁切框':
            l,t,r,b=self._crop_box
            if not hit and not (l<=x<=r and t<=y<=b): return
            self._gesture=('crop',hit or 'move',x,y,(l,t,r,b))
        elif self._handles:
            cx,cy=self._logo_center
            # Accept body drags only inside the actual rotated rectangle.
            a=math.radians(self.wm_rotation.get())
            dx,dy=x-cx,y-cy
            with Image.open(self.watermark_path) as im:
                lw=self._image_size[0]*self.wm_scale.get()/100; lh=im.height*lw/im.width
            if not hit and not (abs(dx*math.cos(a)-dy*math.sin(a))<=lw/2 and abs(dx*math.sin(a)+dy*math.cos(a))<=lh/2): return
            self.wm_mode.set('自由位置')
            self.free_x.set(cx/self._image_size[0]);self.free_y.set(cy/self._image_size[1])
            self._gesture=('logo',hit or 'move',x,y,(cx,cy,self.wm_scale.get(),self.wm_rotation.get()))

    def pointer_move(self,e):
        if not self._gesture: return
        kind,hit,x0,y0,initial=self._gesture
        x,y=self.image_point(e); w,h=self._image_size
        if kind == 'crop':
            l,t,r,b=initial; bw,bh=r-l,b-t
            if hit == 'move':
                l=max(0,min(w-bw,l+x-x0));t=max(0,min(h-bh,t+y-y0))
            else:
                ax = r if 'w' in hit else l; ay = b if 'n' in hit else t
                sx = -1 if 'w' in hit else 1;sy = -1 if 'n' in hit else 1
                factor = max(.02,((x-ax)*sx*bw+(y-ay)*sy*bh)/(bw*bw+bh*bh))
                factor=min(factor,(ax if sx<0 else w-ax)/bw,(ay if sy<0 else h-ay)/bh)
                bw,bh=max(1,bw*factor),max(1,bh*factor)
                l,t=min(ax,ax+sx*bw),min(ay,ay+sy*bh)
            full=crop_box((w,h),base.RATIOS[self.output_ratio.get()])
            z=max(1,(full[2]-full[0])/bw)
            self._crops[self.current_path()]=(l/(w-bw) if w>bw else .5,t/(h-bh) if h>bh else .5,z)
        else:
            cx,cy,scale,angle=initial
            if hit == 'move':
                self.free_x.set(max(0,min(1,(cx+x-x0)/w)));self.free_y.set(max(0,min(1,(cy+y-y0)/h)))
            elif hit == 'rotate':
                delta=math.degrees(math.atan2(y0-cy,x0-cx)-math.atan2(y-cy,x-cx))
                self.wm_rotation.set((angle+delta+180)%360-180)
            else:
                factor=math.hypot(x-cx,y-cy)/max(1,math.hypot(x0-cx,y0-cy))
                self.wm_scale.set(max(1,min(100,scale*factor)))
        self.preview()

    def pointer_up(self,e=None):
        self._gesture=None
        self.preview()

    def reset_crop(self):
        p=self.current_path()
        self._crops.pop(p,None)
        self.crop_x.set(.5);self.crop_y.set(.5)
        self.preview()

    def _append(self,items):
        super()._append([str(Path(p).resolve()) for p in items])
        self.refresh_thumbs()

    def _rebuild_tree(self):
        super()._rebuild_tree()
        self._thumbs.clear()
        self.refresh_thumbs()
        self._crops={p:c for p,c in self._crops.items() if p in self.paths}

    def refresh_thumbs(self):
        # Populate a few thumbnails per event-loop turn so long lists stay responsive.
        pending=[(str(i),p) for i,p in enumerate(self.paths) if p not in self._thumbs]
        def chunk():
            for _ in range(min(6,len(pending))):
                iid,p=pending.pop(0)
                if not self.tree.exists(iid) or int(iid)>=len(self.paths) or self.paths[int(iid)]!=p: continue
                try:
                    with Image.open(p) as im:
                        thumb=ImageOps.exif_transpose(im);thumb.thumbnail((52,52))
                        photo=ImageTk.PhotoImage(thumb.convert('RGBA'))
                    self._thumbs[p]=photo;self.tree.item(iid,image=photo)
                except Exception:
                    LOG.exception('Thumbnail failed: %s',p)
            if pending:self.after(10,chunk)
        self.after(1,chunk)

    def refresh_profiles(self):
        for w in self.multi_frame.winfo_children(): w.destroy()
        self.profile_vars={}
        canvas=tk.Canvas(self.multi_frame,highlightthickness=0,bg='#171a1d',width=320)
        scroll=ttk.Scrollbar(self.multi_frame,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        content=ttk.Frame(canvas)
        window=canvas.create_window(0,0,anchor='nw',window=content)
        content.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        for name,c in self.profiles.items():
            row=ttk.Frame(content);row.pack(fill='x',pady=3)
            var=tk.BooleanVar(self,c.get('enabled',False));self.profile_vars[name]=var
            ttk.Checkbutton(row,text=name,variable=var,command=self._sync_profiles).pack(side='left')
            ttk.Button(row,text='編輯',width=5,command=lambda n=name:self.edit_profile(n)).pack(side='right')
            ttk.Label(content,text=f"{c.get('mode','指定長邊')} · {c.get('format','JPG')} · {c.get('max_kb',0)} KB（0 不限）",style='Muted.TLabel').pack(anchor='w')

    def add_profile(self): self.edit_profile()

    def edit_profile(self,name=None):
        c=dict(self.profiles.get(name,{}) or dict(ratio='4:5',mode='指定長邊',edge=1350,format='JPG',quality=92,enabled=True))
        win=tk.Toplevel(self);win.title('編輯輸出規格' if name else '新增輸出規格');win.transient(self);win.grab_set()
        fields={}
        specs=[('name','規格／子資料夾名稱',name or '',None),('ratio','裁切比例',c.get('ratio','原始比例'),list(base.RATIOS)),('mode','尺寸模式',c.get('mode','指定長邊'),['百分比','指定長邊','指定寬高']),('pct','百分比 %',c.get('pct',100),None),('edge','長邊 px',c.get('edge',2048),None),('width','寬度 px',c.get('width',1080),None),('height','高度 px',c.get('height',1350),None),('fit','指定寬高配置',c.get('fit','裁切填滿'),['裁切填滿','留白符合','等比縮入']),('format','格式',c.get('format','JPG'),['JPG','JPEG','PNG','WEBP']),('quality','JPG / WebP 品質',c.get('quality',92),None),('max_kb','檔案上限 KB（0 不限）',c.get('max_kb',0),None)]
        for i,(key,label,value,choices) in enumerate(specs):
            ttk.Label(win,text=label).grid(row=i,column=0,sticky='w',padx=12,pady=5)
            var=tk.StringVar(win,str(value));fields[key]=var
            widget=ttk.Combobox(win,textvariable=var,values=choices,state='readonly') if choices else ttk.Entry(win,textvariable=var)
            widget.grid(row=i,column=1,padx=12,pady=5,sticky='ew')
        enabled=tk.BooleanVar(win,c.get('enabled',True))
        ttk.Checkbutton(win,text='啟用此規格',variable=enabled).grid(row=11,columnspan=2,sticky='w',padx=12)
        ttk.Label(win,text='指定寬高：填滿使用寬高比例裁切；留白保持畫布尺寸。\n未允許放大時不足部分留白；等比縮入可能小於指定寬高。\n檔案上限維持像素尺寸；無法達成會記錄錯誤，不輸出超標檔案。',wraplength=450).grid(row=12,columnspan=2,padx=12,pady=8)
        def save():
            try:
                values={k:v.get() for k,v in fields.items()};new_name=safe_name(values.pop('name'))
                if any(n.casefold()==new_name.casefold() and n!=name for n in self.profiles):raise ValueError('規格名稱已存在')
                values['enabled']=enabled.get();values=validate_profile(values)
                self._sync_profiles()
                if name and name!=new_name:self.profiles.pop(name)
                self.profiles[new_name]=values
                self._save_json(base.PROFILES_FILE,self.profiles)
                self.refresh_profiles();win.destroy()
            except (ValueError,tk.TclError) as e:messagebox.showerror('設定錯誤',str(e),parent=win)
        ttk.Button(win,text='儲存規格',command=save).grid(row=13,column=1,pady=12)
        ttk.Button(win,text='取消',command=win.destroy).grid(row=13,column=0,pady=12)

    def export(self):
        if self._busy:
            self.status.set('批次處理進行中，請等候或取消');return
        if not self.paths:messagebox.showwarning('提醒','請先加入圖片',parent=self);return
        try:
            self._sync_profiles()
            active=[(safe_name(n),validate_profile(c)) for n,c in self.profiles.items() if c.get('enabled')]
            profiles=active or [(None,self.single_profile())]
            cfg=copy.deepcopy(self.config())
            for key in ('wm_scale','wm_opacity','wm_rotation','margin','free_x','free_y','tile_gap','text_size','text_opacity'):
                if not math.isfinite(float(cfg[key])):raise ValueError(f'{key} 不是有效數值')
            if cfg['text_size']<1 or cfg['wm_scale']<=0:raise ValueError('Logo／文字大小必須大於零')
            self.save_settings()
            source_mode=self.output_to_source.get();sub=safe_name(self._safe_subfolder())
            out=Path(self.output_dir.get()).expanduser()
            if not source_mode:out.mkdir(parents=True,exist_ok=True)
        except Exception as e:
            LOG.exception('Export validation failed');messagebox.showerror('無法開始輸出',str(e),parent=self);return
        self._busy=True;self.cancelled=False;self._stop.clear()
        paths=tuple(self.paths);processor=Processor(cfg,copy.deepcopy(self._crops))
        self.progress.configure(maximum=len(paths)*len(profiles),value=0)
        self._batch_destination=f'各原圖資料夾 / {sub}' if source_mode else str(out)
        self.status.set('開始處理；本次使用啟動時的設定與圖片清單')
        def worker():
            done=skip=step=0;errors=[]
            try:
                for i,src in enumerate(paths):
                    for name,c in profiles:
                        if self._stop.is_set():break
                        try:
                            img,exif=processor.process_profile(src,c)
                            folder=(Path(src).parent/sub) if source_mode else out
                            if name:folder/=name
                            folder.mkdir(parents=True,exist_ok=True)
                            filename=base.App.filename(processor,src,i,img,c['format'])
                            if c['format']=='WEBP':filename=str(Path(filename).with_suffix('.webp'))
                            safe_name(filename)
                            target=processor.resolve(folder/filename)
                            if target is None:skip+=1
                            else:
                                if target.resolve() in {Path(p).resolve() for p in paths}:raise ValueError('輸出位置不可覆蓋匯入的原圖')
                                data=encode_image(img,c['format'],c['quality'],exif if cfg['preserve_exif'] else None,c['max_kb'])
                                if self._stop.is_set():break
                                atomic_write(target,data);done+=1
                        except Exception as e:
                            LOG.exception('Export failed: source=%s profile=%s',src,name)
                            errors.append(f'{Path(src).name} / {name or "單張"}: {e}')
                        step+=1;self._events.put(('progress',step))
                    if self._stop.is_set():break
            finally:self._events.put(('finish',done,skip,errors,self._stop.is_set()))
        threading.Thread(target=worker,daemon=True).start()

    def poll_events(self):
        try:
            while True:
                event=self._events.get_nowait()
                if event[0]=='progress':
                    self.progress.configure(value=event[1]);self.status.set(f'處理中 {event[1]}/{int(self.progress["maximum"])}')
                else:
                    _,done,skip,errors,cancelled=event;self._busy=False
                    self.status.set(('已取消' if cancelled else '完成')+f'：成功 {done} / 略過 {skip} / 錯誤 {len(errors)}')
                    msg=f'{self.status.get()}\n輸出：{self._batch_destination}'
                    if errors:messagebox.showwarning('批次處理結果',msg+'\n\n'+'\n'.join(errors[:8])+'\n完整資訊請查看錯誤日誌',parent=self)
                    else:messagebox.showinfo('批次處理結果',msg,parent=self)
        except queue.Empty:pass
        self.after(100,self.poll_events)

    def cancel(self):
        if self._busy:self._stop.set();self.status.set('正在停止；已完成檔案會保留')

    def close(self):
        if self._busy:
            self.cancel();self.status.set('正在停止，處理結束後可關閉視窗');return
        try:self.save_settings()
        except Exception:LOG.exception('Saving settings on close failed')
        self.destroy()

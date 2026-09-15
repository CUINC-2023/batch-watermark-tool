"""Tk-free export processor. Dimensions are preserved when enforcing byte limits."""
import io
import math
import os
import tempfile
from pathlib import Path
from PIL import Image, ImageOps
import app

FORMATS = ('JPG', 'JPEG', 'PNG', 'WEBP')


def safe_name(name):
    name = str(name).strip()
    if not name or name.endswith(('.', ' ')) or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name):
        raise ValueError('名稱不可空白或包含路徑與特殊字元')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))}:
        raise ValueError('此名稱為 Windows 保留名稱')
    return name


def validate_profile(c):
    c = dict(c)
    if c.get('format') not in FORMATS or c.get('ratio') not in app.RATIOS:
        raise ValueError('請選擇有效格式與比例')
    if c.get('mode') not in ('百分比', '指定長邊', '指定寬高'):
        raise ValueError('尺寸模式錯誤')
    for key, default, lo, hi in [('pct',100,1,400),('edge',2048,1,20000),('width',1080,1,20000),('height',1350,1,20000),('quality',92,1,100),('max_kb',0,0,1048576)]:
        v = float(c.get(key, default))
        if not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f'{key} 必須介於 {lo} 與 {hi}')
        if key not in ('pct','max_kb') and v != int(v):
            raise ValueError(f'{key} 必須為整數')
        c[key] = v if key in ('pct','max_kb') else int(v)
    if c.get('fit', '裁切填滿') not in ('裁切填滿', '留白符合', '等比縮入'):
        raise ValueError('寬高配置方式錯誤')
    return c


def crop_box(size, ratio, cx=.5, cy=.5, zoom=1):
    w,h = size
    target = w/h if not ratio else ratio[0]/ratio[1]
    nw,nh = (h*target,h) if w/h > target else (w,w/target)
    nw,nh = max(1,round(nw/zoom)), max(1,round(nh/zoom))
    l,t = round((w-nw)*max(0,min(1,cx))), round((h-nh)*max(0,min(1,cy)))
    return l,t,l+nw,t+nh


class Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value


class Processor:
    anchor = app.App.anchor
    apply_wm = app.App.apply_wm
    resize = app.App.resize
    resolve = app.App.resolve

    def __init__(self, config, crops=None):
        for k,v in config.items(): setattr(self,k,Value(v))
        self.watermark_path = config.get('watermark_path')
        self.text_color = config.get('text_color','#ffffff')
        self.crops = crops or {}

    def process_profile(self, path, c, processed=True):
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source)
            exif = image.getexif()
            exif.pop(274, None)
            image = image.convert('RGBA')
        cx,cy,z = self.crops.get(str(path), (self.crop_x.get(),self.crop_y.get(),1))
        ratio = app.RATIOS[c['ratio']]
        if c['mode'] == '指定寬高' and c.get('fit','裁切填滿') == '裁切填滿':
            ratio = (c['width'], c['height'])
        image = image.crop(crop_box(image.size,ratio,cx,cy,z))
        if c['mode'] == '指定寬高':
            target = (c['width'],c['height'])
            fit = c.get('fit','裁切填滿')
            scale = min(target[0]/image.width,target[1]/image.height)
            if not self.allow_upscale.get(): scale = min(1,scale)
            image = image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.LANCZOS)
            if fit != '等比縮入':
                bg = Image.new('RGBA',target,(255,255,255,0))
                bg.alpha_composite(image,((target[0]-image.width)//2,(target[1]-image.height)//2))
                image = bg
        else:
            image = self.resize(image,c['mode'],c['pct'],c['edge'])
        if processed: image = self.apply_wm(image)
        for tag in (40962,40963,256,257): exif.pop(tag,None)
        return image, exif.tobytes() if exif else None


def encode_image(image, fmt, quality, exif=None, max_kb=0):
    fmt = fmt.upper()
    if fmt not in FORMATS: raise ValueError('不支援的輸出格式')
    limit = int(max_kb*1024)
    if max_kb and limit < 1: raise ValueError('檔案上限過小')
    if fmt in ('JPG','JPEG'):
        bg = Image.new('RGB',image.size,'white')
        bg.paste(image, mask=image.getchannel('A') if image.mode == 'RGBA' else None)
        image,fmt = bg,'JPEG'
    def encode(q):
        buf = io.BytesIO()
        kw = {'quality':q} if fmt != 'PNG' else {'optimize':True}
        if fmt == 'JPEG': kw['optimize'] = True
        if exif: kw['exif'] = exif
        image.save(buf,format=fmt,**kw)
        return buf.getvalue()
    # Descending search ensures the highest requested-or-lower quality that fits.
    for q in (range(int(quality),0,-1) if limit and fmt != 'PNG' else [int(quality)]):
        data = encode(q)
        if not limit or len(data) <= limit: return data
    raise ValueError('無法在維持像素尺寸下符合檔案上限；請降低尺寸、提高上限或改用 JPG / WebP')


def atomic_write(path, data):
    fd,tmp = tempfile.mkstemp(prefix='.watermark-',dir=Path(path).parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from imaging import crop_box, encode_image, safe_name, validate_profile, Processor, atomic_write


class ImagingTests(unittest.TestCase):
    def test_crop_boundaries(self):
        for size in ((400,300),(300,400),(1,1)):
            for ratio in ((4,5),(16,9),None):
                for x,y in ((0,0),(1,1),(.5,.5)):
                    l,t,r,b=crop_box(size,ratio,x,y,2)
                    self.assertTrue(0<=l<r<=size[0] and 0<=t<b<=size[1])

    def test_formats_and_limit(self):
        im=Image.effect_noise((128,96),100).convert('RGBA')
        for fmt in ('JPG','JPEG','PNG','WEBP'):
            data=encode_image(im,fmt,92)
            with Image.open(io.BytesIO(data)) as saved:
                self.assertEqual(saved.size,im.size)
                self.assertEqual(saved.format,'JPEG' if fmt in ('JPG','JPEG') else fmt)
            with self.assertRaises(ValueError):encode_image(im,fmt,92,max_kb=.01)
        data=encode_image(im,'WEBP',92,max_kb=8)
        self.assertLessEqual(len(data),8192)

    def test_alpha(self):
        im=Image.new('RGBA',(30,30),(255,0,0,0))
        for fmt in ('PNG','WEBP'):
            saved=Image.open(io.BytesIO(encode_image(im,fmt,92)))
            self.assertEqual(saved.convert('RGBA').getpixel((0,0))[3],0)

    def test_validation(self):
        for name in ('../x','CON','LPT1.txt','bad/dir','x.',''):
            with self.assertRaises(ValueError):safe_name(name)
        c=dict(ratio='4:5',mode='指定寬高',format='WEBP')
        self.assertEqual(validate_profile(c)['width'],1080)
        for key,value in (('width',0),('quality',101),('max_kb',float('nan')),('height',1.5)):
            with self.assertRaises(ValueError):validate_profile(dict(c,**{key:value}))

    def test_processing_orientation_and_dimensions(self):
        config=dict(crop_x=.5,crop_y=.5,allow_upscale=False,wm_enabled=False,text_enabled=False)
        processor=Processor(config)
        c=validate_profile(dict(ratio='原始比例',mode='指定寬高',width=80,height=80,format='WEBP',fit='留白符合'))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'oriented.jpg'
            exif=Image.Exif();exif[274]=6
            Image.new('RGB',(120,60),'red').save(path,exif=exif)
            im,metadata=processor.process_profile(path,c)
            self.assertEqual(im.size,(80,80))
            if metadata:
                ex=Image.Exif();ex.load(metadata);self.assertNotIn(274,ex)
            target=Path(d)/'result.webp';atomic_write(target,encode_image(im,'WEBP',92))
            with Image.open(target) as saved: self.assertEqual(saved.format,'WEBP')
            self.assertEqual(len(list(Path(d).glob('.watermark-*'))),0)

if __name__ == '__main__':unittest.main()

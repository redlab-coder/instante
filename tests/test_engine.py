import io
import unittest
from PIL import Image, ImageDraw
from engine import APERTURE, PAGE, PHOTO, render_tile, prepare_photo, normalized_edits, output_names, jpeg_bytes, load_image


class EngineTests(unittest.TestCase):
    def test_physical_geometry_and_cut_strip(self):
        image = render_tile(Image.new('RGB', (945,945), 'blue'))
        self.assertEqual(image.size, PAGE)
        self.assertEqual(APERTURE, (70,59,1015,1004))
        self.assertEqual(image.getpixel((70,59)), (0,0,255))
        self.assertEqual(image.getpixel((1014,1003)), (0,0,255))
        for xy in [(69,59),(1015,1003),(70,58),(70,1004),(1294,10)]:
            self.assertEqual(image.getpixel(xy), (255,255,255))
        for xy in [(1295,0),(1499,1062)]:
            self.assertEqual(image.getpixel(xy), (255,0,0))

    def test_upright_top_becomes_left_and_manual_half_turn_becomes_right(self):
        source = Image.new('RGB', (800,800), 'white')
        draw = ImageDraw.Draw(source)
        draw.rectangle((0,0,799,199),fill='red')
        draw.rectangle((0,600,799,799),fill='blue')
        image = prepare_photo(source)
        self.assertEqual(image.getpixel((20,472)), (255,0,0))
        self.assertEqual(image.getpixel((920,472)), (0,0,255))
        inverse = prepare_photo(source, {'rotation':90})
        self.assertEqual(inverse.getpixel((20,472)), (0,0,255))

    def test_contain_preserves_rectangular_content_and_existing_white(self):
        source = Image.new('RGB', (400,800), 'blue')
        ImageDraw.Draw(source).rectangle((0,0,399,100),fill='white')
        square = prepare_photo(source, {'rotation':0})
        self.assertEqual(square.size, (PHOTO,PHOTO))
        self.assertEqual(square.getpixel((0,472)), (255,255,255))
        self.assertEqual(square.getpixel((472,20)), (255,255,255))
        self.assertEqual(square.getpixel((472,472)), (0,0,255))
        fill = prepare_photo(source, {'rotation':0,'mode':'cover'})
        self.assertEqual(fill.getpixel((20,472)), (0,0,255))

    def test_export_density_profile_and_transparency(self):
        image = render_tile(Image.new('RGB', (300,300), 'blue'))
        with Image.open(io.BytesIO(jpeg_bytes(image))) as result:
            self.assertEqual(result.info['dpi'], (300,300))
            self.assertTrue(result.info['icc_profile'])
            self.assertEqual(result.size, PAGE)
        stream=io.BytesIO();Image.new('RGBA',(10,10),(0,0,0,0)).save(stream,'PNG')
        self.assertEqual(load_image(stream.getvalue()).getpixel((0,0)), (255,255,255))

    def test_invalid_edits_and_collision_safe_names(self):
        for edits in [{'rotation':45},{'mode':'unknown'},{'brightness':float('nan')}]:
            with self.assertRaises(ValueError):normalized_edits(edits)
        self.assertEqual(output_names(['a.jpg','a.png','A.jpg']), ['a-polaroid.jpg','a-polaroid-2.jpg','A-polaroid-3.jpg'])
        self.assertEqual(output_names(['../x.png'])[0], 'x-polaroid.jpg')

    def test_exif_orientation_is_applied_once_before_template_rotation(self):
        source=Image.new('RGB',(800,400),'blue')
        ImageDraw.Draw(source).rectangle((0,0,799,99),fill='red')
        exif=Image.Exif();exif[274]=6
        stream=io.BytesIO();source.save(stream,'PNG',exif=exif)
        loaded=load_image(stream.getvalue())
        self.assertEqual(loaded.size,(400,800))
        self.assertEqual(loaded.getpixel((380,400)),(255,0,0))
        self.assertNotIn(274,loaded.getexif())


if __name__ == '__main__':unittest.main()

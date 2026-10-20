"""Original illustrations for reproducible public screenshots. No client photos."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def font(size, serif=False):
    try:return ImageFont.truetype('georgia.ttf' if serif else 'segoeui.ttf',size)
    except OSError:return ImageFont.load_default(size=size)


def make_demos(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGB',(1200,1200),'#f1ede4');draw=ImageDraw.Draw(image)
    draw.ellipse((480,160,720,400),fill='#c9906c')
    draw.polygon([(0,820),(370,330),(850,940)],fill='#a0b7b7')
    draw.polygon([(200,1000),(820,450),(1200,850),(1200,1200),(0,1200)],fill='#547e86')
    draw.polygon([(0,1100),(540,750),(1200,1050),(1200,1200),(0,1200)],fill='#315b6a')
    draw.text((80,82),'UM LUGAR PARA VOLTAR',font=font(25),fill='#315b6a')
    draw.text((80,1020),'Horizontes',font=font(88,True),fill='#f5f1e8')
    image.save(directory/'Horizontes.png')
    image=Image.new('RGB',(1400,900),'#dfebed');draw=ImageDraw.Draw(image)
    draw.rectangle((0,470,1400,900),fill='#6a9399')
    draw.ellipse((1040,130,1180,270),fill='#c9906c')
    for offset in (540,630,720):draw.arc((-300,offset,1500,offset+240),190,350,fill='#c2d7d9',width=5)
    draw.text((90,110),'Devagar,',font=font(85,True),fill='#315b6a')
    draw.text((90,220),'o dia fica.',font=font(85,True),fill='#315b6a')
    draw.text((90,800),'FEITO PARA GUARDAR',font=font(24),fill='#eff5f6')
    image.save(directory/'Marés.png')
    image=Image.new('RGB',(900,1200),'#315b6a');draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((75,75,825,1125),radius=300,outline='#a3bdc3',width=3)
    draw.ellipse((380,260,520,400),fill='#c9906c')
    draw.text((450,560),'Boas',font=font(68,True),anchor='mm',fill='#f3f1e8')
    draw.text((450,650),'memórias.',font=font(68,True),anchor='mm',fill='#f3f1e8')
    draw.text((450,830),'O QUE IMPORTA FICA.',font=font(21),anchor='mm',fill='#bdd0d5')
    image.save(directory/'Memórias.png')
    return [directory/'Horizontes.png',directory/'Marés.png',directory/'Memórias.png']


if __name__=='__main__':make_demos(Path(__file__).resolve().parents[1]/'tests/artifacts/demo')

from PIL import Image

class ImageCropperService:
    @staticmethod
    def crop_region(image: Image.Image, x: float, y: float, w: float, h: float) -> Image.Image:
        """
        Recorta a região de interesse (Bounding Box) da página renderizada.
        Suporta tanto coordenadas normalizadas (0.0 até 1.0) quanto em pixels absolutos.
        
        Coordenadas Normalizadas são mais seguras pois não dependem do DPI final da renderização.
        """
        img_width, img_height = image.size
        
        # Se w e h forem <= 1.0 assumimos que as coordenadas do banco estão normalizadas
        if w <= 1.0 and h <= 1.0:
            left = int(x * img_width)
            top = int(y * img_height)
            right = int((x + w) * img_width)
            bottom = int((y + h) * img_height)
        else:
            # Caso contrário, assumimos que são pixels absolutos
            left = int(x)
            top = int(y)
            right = int(x + w)
            bottom = int(y + h)
            
        # Garante que as dimensões não extrapolem a imagem original
        left = max(0, left)
        top = max(0, top)
        right = min(img_width, right)
        bottom = min(img_height, bottom)
            
        return image.crop((left, top, right, bottom))

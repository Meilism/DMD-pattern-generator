from PIL import Image, ImageDraw, ImageFont

import math
import numpy as np
import os

from numba import jit
from matplotlib import pyplot as plt

# DMD dimensions
DMD_ROWS = 1140
DMD_COLS = 912

# Whether to filp the image vertically
FLIP = True

def parseRange(x):
    """
    Parse the range argument to a valid range
    --------------------
    Parameters:
    --------------------
    x: int | array-like
        int for number of elements, array-like for list of elements

    --------------------
    Returns:
    --------------------
    x: array-like
        array-like of shape (N,)
    """
    if isinstance(x, int):
        assert x >= 0, 'x must be a non-negative integer'
        x = range(x)
    return x

def parseColor(color):
    """
    Parse the color argument to a valid 24-bit RGB color
    --------------------
    Parameters:
    --------------------
    color: int | float | array-like
        1 for white (on), 0 for black (off), float for grayscale, list or array-like of shape (3,) for RGB
    
    --------------------
    Returns:
    --------------------
    color: RGB color
    """
    if isinstance(color, float) or isinstance(color, int):
        if (color >= 0 and color <= 1):
            color = np.floor(255 * np.array([color, color, color])).astype(np.uint8)
        elif (color >= 0 and color <= 255):
            color = np.floor([color, color, color]).astype(np.uint8)
        else:
            raise ValueError('Invalid color')

    elif (isinstance(color, list) and len(color) == 3) or isinstance(color, np.ndarray):
        color = np.array(color).astype(np.uint8)
        if color.shape == (3,) and np.all(color >= 0) and np.all(color <= 255):
            pass
        else:
            raise ValueError('Invalid color')
        
    else:
        raise ValueError('Invalid color')
    
    return color

def checkVector(vector):
    """
    Check if the given vector is a valid lattice vector
    --------------------
    Parameters:
    --------------------
    vector: list | array-like
        Lattice vector to be checked

    --------------------
    Raises:
    --------------------
    ValueError: if the given vector is not a valid lattice vector
    """
    if isinstance(vector, list):
        assert len(vector) == 2, 'Lattice vector 1 must be a list of length 2'
    elif isinstance(vector, np.ndarray):
        assert vector.shape == (2,), 'Lattice vector 1 must be an array of shape (2,)'
    else:
        raise ValueError('Lattice vector 1 must be a list or numpy array of shape (2,)')

class Frame(object):
    def __init__(self, flip=FLIP) -> None:
        """
        Frame class is used to store the DMD image in a 2D array of 1s and 0s, where 1 
        represents a white pixel (on) and 0 represents a black pixel (off).

        --------------------
        Parameters:
        --------------------
        flip: bool
            True to flip the image vertically, False otherwise.

        --------------------
        Attributes:
        --------------------
        real_array: PIL Image object
            The template image in real space, which is the image that will be converted to DMD space
        dmd_array: PIL Image object
            The DMD image in DMD space, which is the image that will be displayed on the DMD
        flip: bool
            True to flip the image vertically (maybe necessary to get the right conversion), False otherwise
        dmd_nrows: int
            Number of rows in the DMD image
        dmd_ncols: int
            Number of columns in the DMD image
        real_nrows: int
            Number of rows in the real space image
        real_ncols: int
            Number of columns in the real space image
        dmd_rows: array-like of shape (N,)
            Row coordinates of the pixels in the DMD image
        dmd_cols: array-like of shape (N,)
            Column coordinates of the pixels in the DMD image
        bg_rows: array-like of shape (M,)
            Row coordinates of the pixels outside the DMD image
        bg_cols: array-like of shape (M,)
            Column coordinates of the pixels outside the DMD image
        """
        self.dmd_nrows = DMD_ROWS
        self.dmd_ncols = DMD_COLS
        self.flip = flip

        self.real_nrows = math.ceil((self.dmd_nrows-1) / 2) + self.dmd_ncols
        self.real_ncols = self.dmd_ncols + (self.dmd_nrows-1) // 2

        # Initialize the template image in real space to red and the DMD image in DMD space
        self.real_array = np.full((self.real_nrows, self.real_ncols, 3), (255, 0, 0), dtype=np.uint8)
        self.dmd_array = np.full((self.dmd_nrows, self.dmd_ncols, 3), 0, dtype=np.uint8)

        row, col = np.meshgrid(np.arange(self.dmd_nrows), np.arange(self.dmd_ncols), indexing='ij')
        self.dmd_rows, self.dmd_cols = self.realSpace(row.flatten(), col.flatten())

        mask = np.full((self.real_nrows, self.real_ncols), True, dtype=bool)
        mask[self.dmd_rows, self.dmd_cols] = False

        real_row, real_col = np.meshgrid(np.arange(self.real_nrows), np.arange(self.real_ncols), indexing='ij')
        self.bg_rows, self.bg_cols = real_row[mask], real_col[mask]
       
        if self.bg_rows.shape[0] + self.dmd_rows.shape[0] != self.real_nrows * self.real_ncols:
            raise ValueError('Number of pixels in the DMD image does not match the number of pixels in the real space image')

    def realSpace(self, row, col):
        """
        Convert the given DMD space row and column to real space row and column
        --------------------
        Parameters:
        --------------------
        row: int | array-like
            Row in DMD space
        col: int | array-like
            Column in DMD space
        flip: bool
            True to flip the image vertically, False otherwise
        
        --------------------
        Returns:
        --------------------
        real_row: int | array-like
            Row in real space
        real_col: int | array-like
            Column in real space
        """        
        if self.flip: 
            real_row, real_col = (np.ceil((self.dmd_nrows - 1 - row)/2)).astype(int) + col, self.dmd_ncols - 1 + (self.dmd_nrows - 1 - row)//2 - col
        else:
            real_row, real_col = (np.ceil(row/2)).astype(int) + col, self.dmd_ncols - 1 + row//2 - col

        return real_row, real_col
    
    def setRealArray(self, color=1):
        """
        Set the real-space array image to a solid color
        --------------------
        Parameters:
        --------------------
        color: float | array-like
            1 for white (on), 0 for black (off), float for grayscale, list or array-like of shape (3,) for RGB
        """
        color = parseColor(color)

        # Paint all pixels within DMD space to white/black, default is white (on)
        self.real_array[self.dmd_rows, self.dmd_cols, :] = color

        # Paint all pixels outside DMD space to red
        self.real_array[self.bg_rows, self.bg_cols, :] = np.array([255, 0, 0])

        # Convert the template image to DMD array
        self.dmd_array[:] = color
    
    def getTemplateImage(self):
        """
        Return a PIL Image object of the real-space image with labels on the corners
        --------------------
        Parameters:
        --------------------
        color: int
            1 for white (on), 0 for black (off)
        
        --------------------
        Returns:
        --------------------
        template: PIL Image object
            The template image in real space
        """
        image = Image.fromarray(self.real_array, mode='RGB')
        
        # Add labels on the corners
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("arial.ttf", 30)

        if self.flip:
            offset = ((150, -150), (0, 50), (150, 0))
        else:
            offset = ((0, -100), (150, -150), (-50, 50))

        corner00 = self.realSpace(0, 0)[1] + offset[0][1], self.realSpace(0, 0)[0] + offset[0][0]
        corner10 = self.realSpace(self.dmd_nrows-1, 0)[1] + offset[1][1], self.realSpace(self.dmd_nrows-1, 0)[0] + offset[1][0]
        corner11 = self.realSpace(self.dmd_nrows-1, self.dmd_ncols-1)[1] + offset[2][1], self.realSpace(self.dmd_nrows-1, self.dmd_ncols-1)[0] + offset[2][0]

        draw.text(corner00, '(0, 0)', font=font, fill=0)
        draw.text(corner10, f'({self.dmd_nrows-1}, 0)', font=font, fill=0)
        draw.text(corner11, f'({self.dmd_nrows-1}, {self.dmd_ncols-1})', font=font, fill=0)
        return image

    def loadRealImage(self, image: Image.Image):
        """
        Load the given real space image to the real-space array and convert it to DMD space
        --------------------
        Parameters:
        --------------------
        image: PIL Image object
            The real space image to be converted to DMD space
        """
        assert image.size == (self.real_ncols, self.real_nrows), 'Image size does not match DMD template size'
        self.real_array[:, :, :] = np.asarray(image, dtype=np.uint8)
        self.updateDmdArray()
    
    def updateDmdArray(self):
        """
        Update the DMD array from the real-space array
        """
        # Loop through every column and row for the DMD image and assign it 
        # the corresponding pixel value from the real space image
        self.dmd_array[:, :, :] = self.real_array[self.dmd_rows, self.dmd_cols, :].reshape(self.dmd_nrows, self.dmd_ncols, 3)
    
    def saveDmdArrayToImage(self, dir, filename):
        """
        Save the DMD array to a BMP file
        --------------------
        Parameters:
        --------------------
        filename: str
            Name of the BMP file to be saved
        """
        if os.path.exists(dir) == False:
            os.makedirs(dir)
        dmd_filename = dir + 'pattern_' + filename
        template_filename = dir + 'template_' + filename

        image = Image.fromarray(self.dmd_array, mode='RGB')
        image.save(dmd_filename, mode='RGB')
        print('DMD pattern saved as', dmd_filename)

        image = self.getTemplateImage()
        image.save(template_filename, mode='RGB')
        print('Template image saved as', template_filename)
    
    def drawPattern(self, 
                    corr, 
                    color=1, 
                    reset=True, 
                    template_color=None, 
                    bg_color=np.array([255, 0, 0])):
        """
        Draw a pattern on the DMD image at the given coordinates
        --------------------
        Parameters:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the pattern
        color: int | array-like, color of the pattern
            1 for white (on), 0 for black (off)
        reset: bool
            True to reset the real space template to the default template, False otherwise

        --------------------
        Returns:
        --------------------
        template: PIL Image object
            The template image in real space
        """
        # Reset the real space template
        color = parseColor(color)
        if reset: 
            if template_color is None:
                # The default template background color is the inverse of the pattern color
                template_color = np.array([255, 255, 255]) - color
            self.setRealArray(color=template_color)
        
        # Draw a binary pattern on real-space array
        self.real_array[corr[:, 0], corr[:, 1]] = color          

        # Fill the background space with red
        self.real_array[self.bg_rows, self.bg_cols, :] = parseColor(bg_color)

        # Update the pixels in DMD space from the updated real-space array
        self.updateDmdArray()

    def simulateImage(self, wavelength=532,):
        image = self.real_array.sum(axis=2)
        image[self.bg_rows, self.bg_cols] = 0
        
class Dither(object):
    
    @staticmethod
    def normalizePattern(image: np.ndarray):
        """
        Normalize the stored pattern to [0, 1]

        --------------------
        Returns:
        --------------------
        image: np.array of shape (height, width), dtype=float, 0.0-1.0
        """
        max_val = image.max()
        min_val = image.min()
        if max_val == min_val:
            image.fill(0)
        else:
            np.copyto(image, (image - min_val) / (max_val - min_val))

    @staticmethod
    @jit(nopython=True)
    def floyd_steinberg(image: np.ndarray):
        """
        Floyd-Steinberg dithering algorithm.
        https://en.wikipedia.org/wiki/Floyd–Steinberg_dithering
        https://gist.github.com/bzamecnik/33e10b13aae34358c16d1b6c69e89b01
        --------------------
        Parameters:
        --------------------
        image: np.array of shape (height, width), dtype=float, 0.0-1.0
            works in-place!
        --------------------
        Returns:
        --------------------
        image: np.array of shape (height, width), dtype=float, 0.0-1.0
        """
        
        h, w = image.shape        
        for y in range(h):
            for x in range(w):
                old = image[y, x]
                new = np.round(old)
                image[y, x] = new
                error = old - new

                # precomputing the constants helps
                if x + 1 < w:
                    image[y, x + 1] += error * 0.4375 # right, 7 / 16
                if (y + 1 < h) and (x + 1 < w):
                    image[y + 1, x + 1] += error * 0.0625 # right, down, 1 / 16
                if y + 1 < h:
                    image[y + 1, x] += error * 0.3125 # down, 5 / 16
                if (x - 1 >= 0) and (y + 1 < h): 
                    image[y + 1, x - 1] += error * 0.1875 # left, down, 3 / 16
        
        return image
    
    @staticmethod
    def cutoff(image: np.ndarray, threshold=0.5):
        """
        Cutoff dithering algorithm
        --------------------
        Parameters:
        --------------------
        image: np.array of shape (height, width), dtype=float, 0.0-1.0
        threshold: float
            Threshold for the cutoff dithering algorithm
        --------------------
        Returns:
        --------------------
        image: np.array of shape (height, width), dtype=float, 0.0-1.0
        """
        mask = image >= threshold
        image[mask] = 1
        image[~mask] = 0
        return image
    
    @staticmethod
    def random(image: np.ndarray):
        """
        Random dithering algorithm
        --------------------
        Parameters:
        --------------------
        image: np.array of shape (height, width), dtype=float, 0.0-1.0
        --------------------
        Returns:
        --------------------
        image: np.array of shape (height, width), dtype=float, 0.0-1.0
        """
        mask = (image > np.random.random(image.shape))
        image[mask] = 1
        image[~mask] = 0
        return image

class Painter(object):
    def __init__(self, 
                 nrows, 
                 ncols) -> None:
        """
        Painter class is used to generate coordinates of patterns on a rectangular grid.
        The "draw" functions return the coordinates of the points in the pattern.
        --------------------
        Parameters:
        --------------------
        nrows: int
            Number of rows in the rectangular grid
        ncols: int
            Number of columns in the rectangular grid
        dither_method: str
            Dithering method to use when converting a gray scale image to a binary image
            'Floyd-Steinberg': Floyd-Steinberg dithering algorithm
            'cutoff': Cutoff dithering algorithm
            'random': Random dithering algorithm
        """
        self.nrows = nrows
        self.ncols = ncols
    
    def drawCircle(self, 
                   row_offset=0, 
                   col_offset=0, 
                   radius=50):
        """
        Draw a filled circle on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_offset: int
            Row offset of the center of the circle
        col_offset: int
            Column offset of the center of the circle
        radius: int
            Radius of the circle

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the circle
        """
        # Find the center coordinates
        center_row, center_col = self.nrows // 2, self.ncols // 2
        row, col = center_row + row_offset, center_col + col_offset

        # Draw a filled circle with the given radius
        ans = [(i, j) for i in range(max(0, int(row-radius)), min(int(row+radius+1), self.nrows))\
                for j in range(max(0, int(col-radius)), min(int(col+radius+1), self.ncols)) \
                if (i-row)**2 + (j-col)**2 <= radius**2]
        return np.array(ans)
    
    def drawArrayOfCircles(self, 
                          row_spacing=50, 
                          col_spacing=50, 
                          row_offset=0, 
                          col_offset=0, 
                          nx=5, 
                          ny=5, 
                          radius=1):
        """
        Draw an array of circles on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_spacing: int
            Spacing between rows of circles
        col_spacing: int
            Spacing between columns of circles
        row_offset: int
            Row offset of the center of the first circle
        col_offset: int
            Column offset of the center of the first circle
        nx: int
            Number of circles in each row
        ny: int
            Number of circles in each column
        radius: int
            Radius of the circles

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the arrays of circles
        """
        nx = parseRange(nx)
        ny = parseRange(ny)
        corr = []
        for i in nx:
            for j in ny:
                new_circle = self.drawCircle(row_offset=i*row_spacing+row_offset, 
                                        col_offset=j*col_spacing+col_offset, 
                                        radius=radius)
                if new_circle.shape[0] != 0:
                    corr.append(new_circle)
        return np.concatenate(corr, axis=0)
    
    def drawHorizontalLine(self, row_offset=0, half_width=1):
        """
        Draw a horizontal line on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_offset: int
            Row offset of the center of the line
        half_width: int
            Half width of the line
        
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the line
        """
        # Find the center coordinates
        row = self.nrows // 2 + row_offset
        ans = np.array([(row + i, j) for j in range(self.ncols) for i in range(-half_width, half_width + 1) if row + i < self.nrows and row + i >= 0])
        return ans
    
    def drawVerticalLine(self, col_offset=0, half_width=1):
        """
        Draw a vertical line on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_offset: int
            Row offset of the center of the line
        half_width: int
            Half width of the line
        
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the line
        """
        # Find the center coordinates
        col = self.ncols // 2 + col_offset
        ans = np.array([(i, col + j) for i in range(self.nrows) for j in range(-half_width, half_width + 1) if col + j < self.ncols and col + j >= 0])
        return ans
    
    def drawCross(self, row_offset=0, col_offset=0, half_width=1):
        """
        Draw a cross on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_offset: int
            Row offset of the center of the cross
        col_offset: int
            Column offset of the center of the cross
        half_width: int
            Half width of the lines in the cross

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the cross
        """
        return np.concatenate((self.drawHorizontalLine(row_offset=row_offset, half_width=half_width),
                               self.drawVerticalLine(col_offset=col_offset, half_width=half_width)), axis=0)
    
    def drawHorizontalLines(self, row_spacing=50, row_offset=0, half_width=1, ny=5):
        """
        Draw an array of horizontal lines on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_spacing: int
            Spacing between rows of lines
        row_offset: int
            Row offset of the center of the first line
        half_width: int
            Half width of the lines
        ny: int | array-like
            Number of lines, or a list of row indices to draw lines on
        
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the array of lines
        """
        ny = parseRange(ny)
        corr = []
        for i in ny:
            new_line = self.drawHorizontalLine(row_offset=i*row_spacing+row_offset, 
                                        half_width=half_width)
            if new_line.shape[0] != 0:
                corr.append(new_line)
        return np.concatenate(corr, axis=0)
    
    def drawVerticalLines(self, col_spacing=50, col_offset=0, half_width=1, nx=5):
        """
        Draw an array of vertical lines on the rectangular grid
        --------------------
        Parameters:
        --------------------
        col_spacing: int
            Spacing between columns of lines
        col_offset: int
            Column offset of the center of the first line
        half_width: int
            Half width of the lines
        nx: int | array-like
            Number of lines, or a list of column indices to draw lines on
                  
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the array of lines
        """
        nx = parseRange(nx)
        corr = []
        for j in nx:
            new_line = self.drawVerticalLine(col_offset=j*col_spacing+col_offset, 
                                        half_width=half_width)
            if new_line.shape[0] != 0:
                corr.append(new_line)
        return np.concatenate(corr, axis=0)
    
    def drawAngledLine(self, angle=45, row_offset=0, col_offset=0, half_width=10):
        """
        Draw an angled line on the rectangular grid
        --------------------
        Parameters:
        --------------------
        angle: int
            Angle of the line in degrees
        row_offset: int
            Row offset of the center of the line
        col_offset: int
            Column offset of the center of the line
        half_width: int
            Half width of the line

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the line
        """
        angle = angle % 180

        # Find the center coordinates
        center_row, center_col = self.nrows // 2 + row_offset, self.ncols // 2 + col_offset

        if angle == 0:
            return self.drawHorizontalLine(row_offset=row_offset, half_width=half_width)
        elif angle == 90:
            return self.drawVerticalLine(col_offset=col_offset, half_width=half_width)
        
        # Draw a line with the given angle
        angle = np.deg2rad(angle)
        rows, cols = np.meshgrid(np.arange(self.nrows), np.arange(self.ncols), indexing='ij')
        mask = (np.abs((cols - center_col) * np.sin(angle) - (rows - center_row) * np.cos(angle)) <= half_width).astype(bool).flatten()
        
        return np.stack((rows.flatten()[mask], cols.flatten()[mask])).transpose()
    
    def drawCrosses(self, 
                    row_spacing=50, 
                    col_spacing=50, 
                    row_offset=0, 
                    col_offset=0, 
                    half_width=1, 
                    nx=5, 
                    ny=5):
        """
        Draw an array of crosses on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_spacing: int
            Spacing between rows of crosses
        col_spacing: int
            Spacing between columns of crosses
        row_offset: int
            Row offset of the center of the first cross
        col_offset: int
            Column offset of the center of the first cross
        half_width: int
            Half width of the lines in the crosses
        nx: int
            Number of crosses in each row
        ny: int
            Number of crosses in each column
        
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the array of crosses
        """
        nx = parseRange(nx)
        ny = parseRange(ny)
        corr = [self.drawHorizontalLines(row_spacing=row_spacing, row_offset=row_offset, half_width=half_width, ny=ny),
                self.drawVerticalLines(col_spacing=col_spacing, col_offset=col_offset, half_width=half_width, nx=nx)]

        return np.concatenate(corr, axis=0)
    
    def drawAngledCross(self,
                        angle=45,
                        row_offset=0,
                        col_offset=0,
                        half_width=10):
        """
        Draw an angled cross on the rectangular grid
        --------------------
        Parameters:
        --------------------
        angle: float
            Angle of the cross in degrees
        row_offset: int
            Row offset of the center of the cross
        col_offset: int
            Column offset of the center of the cross
        half_width: int
            Half width of the lines in the cross

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the cross
        """
        return np.concatenate((self.drawAngledLine(angle=angle, row_offset=row_offset, col_offset=col_offset, half_width=half_width),
                               self.drawAngledLine(angle=angle+90, row_offset=row_offset, col_offset=col_offset, half_width=half_width)), axis=0)

    def drawStar(self, row_offset=0, col_offset=0, num=10):
        """
        Draw a star on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_offset: int
            Row offset of the center of the star
        col_offset: int
            Column offset of the center of the star
        num: int
            Number of different sectors in the star

        --------------------
        Returns:
        --------------------
        corr: int
            Coordinates of the points in the star
        """
        # Find the center coordinates
        center_row, center_col = self.nrows // 2 + row_offset, self.ncols // 2 + col_offset

        # Draw a star with the given number of sectors
        angle = 2 * np.pi / num
        rows, cols = np.meshgrid(np.arange(self.nrows), np.arange(self.ncols), indexing='ij')
        mask = ((np.arctan2(cols.flatten() - center_col, rows.flatten() - center_row) // angle) % 2).astype(bool)
        
        return np.stack((rows.flatten()[mask], cols.flatten()[mask])).transpose()
    
    def drawCheckerBoard(self, size=20):
        """
        Draw a checker board on the rectangular grid

        --------------------
        Parameters:
        --------------------
        size: int
            Side length of one checker board square
        
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the checker board
        """
        rows, cols = np.meshgrid(np.arange(self.nrows), np.arange(self.ncols), indexing='ij')
        mask = ((rows.flatten() // size) % 2 + (cols.flatten() // size) % 2) % 2
        return np.stack((rows.flatten()[mask.astype(bool)], cols.flatten()[mask.astype(bool)])).transpose()
    
    def drawSquare(self, radius=3, row_offset=0, col_offset=0):
        """
        Draw a square on the rectangular grid
        --------------------
        Parameters:
        --------------------
        radius: int
            Radius of the square
        row_offset: int
            Row offset of the center of the square
        col_offset: int
            Column offset of the center of the square

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the square
        """
        center_row, center_col = self.nrows // 2 + row_offset, self.ncols // 2 + col_offset

        ans = [(i, j) for i in range(max(0, center_row - radius), min(center_row + radius + 1, self.nrows))\
                for j in range(max(0, center_col - radius), min(center_col + radius + 1, self.ncols))]
        
        return np.array(ans).astype(int)
    
    def drawArrayOfSquares(self, row_spacing=50, col_spacing=50, row_offset=0, col_offset=0, nx=5, ny=5, radius=3):
        """
        Draw an array of squares on the rectangular grid

        --------------------
        Parameters:
        --------------------
        row_spacing: int
            Spacing between rows of squares
        col_spacing: int
            Spacing between columns of squares
        row_offset: int
            Row offset of the center of the first square
        col_offset: int
            Column offset of the center of the first square
        nx: int
            Number of squares in each row
        ny: int
            Number of squares in each column
        radius: int
            Radius of the squares

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the array of squares
        """
        nx = parseRange(nx)
        ny = parseRange(ny)
        
        corr = []
        for i in nx:
            for j in ny:
                new_square = self.drawSquare(row_offset=i*row_spacing+row_offset, 
                                        col_offset=j*col_spacing+col_offset, 
                                        radius=radius)
                if new_square.shape[0] != 0:
                    corr.append(new_square)
        return np.concatenate(corr, axis=0)
    
    def drawHorizontalStrip(self, width=5, row_offset=0):
        """
        Draw a horizontal strip on the rectangular grid
        --------------------
        Parameters:
        --------------------
        width: int
            Width of the strip
        row_offset: int
            Row offset of the top of the strip

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the strip
        """
        center_row = self.nrows // 2 + row_offset
        assert center_row >= 0 and center_row < self.nrows - width, 'Row offset out of range'
        ans = np.array([(center_row + i, j) for j in range(self.ncols) for i in range(width)])
        return ans
    
    def drawVerticalStrip(self, width=5, col_offset=0):
        """
        Draw a vertical strip on the rectangular grid
        --------------------
        Parameters:
        --------------------
        width: int
            Width of the strip
        col_offset: int
            Column offset of the left of the strip

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the strip
        """
        center_col = self.ncols // 2 + col_offset
        assert center_col >= 0 and center_col < self.ncols - width, 'Column offset out of range'
        ans = np.array([(i, center_col + j) for i in range(self.nrows) for j in range(width)])
        return ans
    
    def drawHorizontalStrips(self, width=5, row_offset=0):
        """
        Draw an array of horizontal strips on the rectangular grid
        --------------------
        Parameters:
        --------------------
        width: int
            Width of the strips
        row_offset: int
            Row offset of the top of the first strip

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the array of strips
        """
        corr = [self.drawHorizontalStrip(width=width, row_offset=i-self.nrows//2) for i in range(row_offset, self.nrows - width, 2*width)]
        return np.concatenate(corr, axis=0)
    
    def drawVerticalStrips(self, width=5, col_offset=0):
        """
        Draw an array of vertical strips on the rectangular grid
        --------------------
        Parameters:
        --------------------
        width: int
            Width of the strips
        col_offset: int
            Column offset of the left of the first strip

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the array of strips
        """
        corr = [self.drawVerticalStrip(width=width, col_offset=j-self.ncols//2) for j in range(col_offset, self.ncols - width, 2*width)]
        return np.concatenate(corr, axis=0)
    
    def drawHorizontalHalfPlane(self,
                                row_offset=0,
                                ):
        """
        Draw a horizontal half plane on the rectangular grid
        --------------------
        Parameters:
        --------------------
        row_offset: int
            row offset of the half plane
        
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the half plane
        """
        center_row = self.nrows // 2 + row_offset
        assert center_row >= 0 and center_row < self.nrows, 'Row offset out of range'
        ans = np.array([(i, j) for i in range(center_row, self.nrows) for j in range(self.ncols)])
        return ans

    def drawVerticalHalfPlane(self,
                              col_offset=0,
                              ):
        """
        Draw a vertical half plane on the rectangular grid
        --------------------
        Parameters:
        --------------------
        col_offset: int
            column offset of the half plane

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the half plane
        """
        center_col = self.ncols // 2 + col_offset
        assert center_col >= 0 and center_col < self.ncols, 'Column offset out of range'
        ans = np.array([(i, j) for i in range(self.nrows) for j in range(center_col, self.ncols)])
        return ans
    
    def drawAnchorCircles(self,
                          anchor=((0, 0), (200, 0), (0, 250)),
                          radius=10
                          ):
        """
        Draw anchor circles on the rectangular grid
        --------------------
        Parameters:
        --------------------
        anchor: array-like of shape (N, 2)
            coordinates of the anchor circles
        radius: int
            radius of the anchor circles

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the anchor circles
        """
        corr = []
        for x, y in anchor:
            corr.append(self.drawCircle(row_offset=x, 
                                        col_offset=y, 
                                        radius=radius))
        return np.concatenate(corr, axis=0)

    def drawAnchorCirclesWithBackgroundCircles(self, 
                                                bg_spacing=50,
                                                bg_radius=2,
                                                anchor=((0, 0), (200, 0), (0, 250)),
                                                anchor_radius=5):
        """
        Draw anchor circles with background circles on the rectangular grid
        --------------------
        Parameters:
        --------------------
        bg_spacing: int
            Spacing between rows and columns of background circles
        bg_radius: int
            Radius of the background circles
        anchor: array-like of shape (N, 2)
            coordinates of the anchor circles
        anchor_radius: int
            Radius of the anchor circles

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the anchor circles with background circles
        """
        corr = [self.drawArrayOfCircles(row_spacing=bg_spacing, 
                                        col_spacing=bg_spacing, 
                                        row_offset=0, 
                                        col_offset=0, 
                                        nx=range(-20, 20), 
                                        ny=range(-20, 20), 
                                        radius=bg_radius),
                self.drawAnchorCircles(anchor=anchor, radius=anchor_radius)]
        return np.concatenate(corr, axis=0)

class DitheredPainter(Painter):
    def __init__(self, nrows, ncols, dither_method='Floyd-Steinberg') -> None:
        super().__init__(nrows, ncols)
        
        if dither_method == 'Floyd-Steinberg':
            self.dither = Dither.floyd_steinberg
        elif dither_method == 'cutoff':
            self.dither = Dither.cutoff
        elif dither_method == 'random':
            self.dither = Dither.random
        else:
            raise ValueError('Invalid dithering method')
        
        self.pattern = np.zeros((nrows, ncols))
        self.pattern_binary = np.zeros((nrows, ncols))
        self.rows, self.cols = np.meshgrid(np.arange(self.nrows), np.arange(self.ncols), indexing='ij')
    
    def displayPattern(self):
        """
        Display the stored grayscale pattern and the dithered binary pattern
        """
        plt.figure(figsize=(16, 8))
        plt.subplot(121)
        plt.imshow(self.pattern, cmap='gray')
        plt.xticks([])
        plt.yticks([])
        plt.title('Grayscale pattern')

        plt.subplot(122)
        plt.imshow(self.pattern_binary, cmap='gray')
        plt.xticks([])
        plt.yticks([])
        plt.title('Binary pattern')

        plt.tight_layout()
        plt.show()

    def draw1dLattice(self,
                      lat_vec=[0.01, 0.01],
                      x_offset=0,
                      y_offset=0,
                      ):
        """
        Draw a 1D lattice on the rectangular grid. The intensity is given by cos(2*\pi*k*x) where k is the lattice vector.
        --------------------
        Parameters:
        --------------------
        lat_vec: array-like of shape (2,)
            Lattice vector of the lattice
        
        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the lattice, ditthered to binary image
        """
        checkVector(lat_vec)
        center_row, center_col = self.nrows // 2 + x_offset, self.ncols // 2 + y_offset

        # Update the 2D array with grayscale pattern
        self.pattern = np.cos(2 * np.pi * (lat_vec[0]*(self.rows - center_row) + lat_vec[1]*(self.cols - center_col)))
        Dither.normalizePattern(self.pattern)

        # Dither to binary image
        self.pattern_binary = self.dither(self.pattern.copy())

        # Find the coordinates of the points in the lattice
        mask = (self.pattern_binary == 1).flatten()
        return np.stack((self.rows.flatten()[mask], self.cols.flatten()[mask])).transpose()
    
    def draw2dLattice(self,
                      lat_vec1 = [0.01, 0.],
                      lat_vec2 = [0., 0.01],
                      x_offset=0, 
                      y_offset=0,
                      interference=False,
                      ):
        """
        Draw a 2D lattice on the rectangular grid. The intensity is given by cos(k1*x) + cos(k2*x) + {cos((k1-k2)*x)} where k1, k2 is the lattice vector.
        --------------------
        Parameters:
        --------------------
        lat_vec1: array-like of shape (2,)
            Lattice vector of the first lattice beam
        lat_vec2: array-like of shape (2,)
            Lattice vector of the second lattice beam
        x_offset: int
            Row offset of the center of the lattice
        y_offset: int
            Column offset of the center of the lattice
        interference: bool
            True to add interference term to the lattice

        --------------------
        Returns:
        --------------------
        corr: array-like of shape (N, 2)
            Coordinates of the points in the lattice, ditthered to binary image
        """
        checkVector(lat_vec1)
        checkVector(lat_vec2)
        center_row, center_col = self.nrows // 2 + x_offset, self.ncols // 2 + y_offset

        # Update the 2D array with grayscale pattern
        if not interference:
            self.pattern = np.cos(2 * np.pi * (lat_vec1[0]*(self.rows - center_row) + lat_vec1[1]*(self.cols - center_col))) + \
                        np.cos(2 * np.pi * (lat_vec2[0]*(self.rows - center_row) + lat_vec2[1]*(self.cols - center_col)))
        else:
            self.pattern = np.cos(2 * np.pi * (lat_vec1[0]*(self.rows - center_row) + lat_vec1[1]*(self.cols - center_col))) + \
                        np.cos(2 * np.pi * (lat_vec2[0]*(self.rows - center_row) + lat_vec2[1]*(self.cols - center_col))) + \
                        np.cos(2 * np.pi * ((lat_vec1[0] - lat_vec2[0])*(self.rows - center_row) + (lat_vec1[1] - lat_vec2[1])*(self.cols - center_col)))
        Dither.normalizePattern(self.pattern)

        # Dither to binary image
        self.pattern_binary = self.dither(self.pattern.copy())

        # Find the coordinates of the points in the lattice
        mask = (self.pattern_binary == 1).flatten()
        return np.stack((self.rows.flatten()[mask], self.cols.flatten()[mask])).transpose()
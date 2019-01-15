'''
PYTRX FILEHANDLER MODULE

This script is part of PyTrx, an object-oriented programme created for the 
purpose of calculating real-world measurements from oblique images and 
time-lapse image series.

This module, FileHandler, contains all the functions called by an object to 
load and export data.

Key functions
readMask:               Function to create a mask for point seeding using PIL 
                        to rasterize polygon. The mask is manually defined by 
                        the user using the pyplot ginput function. This 
                        subsequently returns the manually defined area as a 
                        .jpg mask. The writeMask file path is used to either 
                        open the existing mask at that path or to write the 
                        generated mask to this path.
readCalib:              Function to find camera calibrations from a file given 
                        a list or Matlab file containing the required 
                        parameters. Returns the parameters as a dictionary 
                        object.
lineSearch:             Function to supplement the readCalib function. Given an 
                        input parameter to search within the file, this will 
                        return the line numbers of the data.
returnData:             Function to supplement the importCalibration function. 
                        Given the line numbers of the parameter data (the ouput 
                        of the lineSearch function), this will return the data.
readMatrixDistortion:   Function to support the calibrate function. Returns the 
                        intrinsic matrix and distortion parameters required for 
                        calibration from a given file.
checkMatrix:            Function to support the calibrate function. Checks and 
                        converts the intrinsic matrix to the correct format for 
                        calibration with OpenCV.
readImg:                Function to prepare an image by opening, equalising, 
                        converting to either grayscale or a specified band, 
                        then returning a copy.
readGCPs:               Function to read ground control points from a .txt 
                        file. The data in the file is referenced to under a 
                        header line. Data is appended by skipping the header 
                        line and finding the world and image coordinates from 
                        each line.
writeVeloFile:          Function to write all velocity data.
writeHomogFile:         Function to write all homography data.
writeAreaFile:          Function to write all area data (if it has been 
                        calculated) to separate .txt files containing the pixel
                        extents, polygon pixel coordinates, xyz polygon areas,
                        cumulative areas of all polygons, and polygon xyz 
                        coordinates. All these output files are compatible with 
                        the importing tools, namely importAreaData.
WriteLineFile:          Function to write all line data (if it has been 
                        calculated) to separate .txt files containing the pixel
                        coordinates of the lines, the pixel line length, the
                        xyz coordinates of the lines, and the real (xyz) line 
                        lengths. All these output files are compatible with the 
                        importing tools, namely importLineData.
writeVeloSHP:           Function to write OGR points representing velocities 
                        (from ALL images) to file in a .shp file type that is 
                        compatible with mapping sofrware such as ArcMap and 
                        QGIS.
writeAreaSHP:           Function to write OGR polygons (from ALL images) to 
                        file in a .shp file type that is compatible with 
                        mapping sofrware such as ArcMap and QGIS.
writeLineSHP:           Function to write OGR line features (from ALL images) 
                        to file in a .shp file type that is compatible with 
                        mapping sofrware such as ArcMap and QGIS.
importAreaData:         Function to get xyz and px area data from text files 
                        and import it into a specified Measure.Area class 
                        object. This uses the importAreaXYZ and 
                        importAreaPX functions, which are also contained within
                        this FileHandler script. All imported data is held in 
                        the Area class object specified as an input variable. 
                        This can be easily retrieved from the Area class object 
                        itself.
importLineData:         Function to get xyz and px line data from text files 
                        and import into a specified Measure.Line class object.
                        This uses the importLineXYZ and importLinePX functions,
                        which are also contained within this FileHandler 
                        script. All imported data is held in the Line class 
                        object specified as an input variable. This can be 
                        easily retrieved from the Line class object itself.
                        
@author: Penny How (p.how@ed.ac.uk)
         Nick Hulton 
         Lynne Buie
'''

#Import packages
from PIL import Image, ImageDraw
import numpy as np
import operator
import matplotlib.pyplot as plt
import scipy.io as sio
from osgeo import ogr,osr
import os

#------------------------------------------------------------------------------   

def readMask(img, writeMask=None):
    '''Function to create a mask for point seeding using PIL to rasterize 
    polygon. The mask is manually defined by the user using the pyplot ginput 
    function. This subsequently returns the manually defined area as a .jpg 
    mask. 
    
    The writeMask file path is used to either open the existing mask at that 
    path or to write the generated mask to this path.
    
    Variables
    img (arr):          Image to define mask in
    writeMask (str):    File destination that mask output is written to
    
    Returns
    myMask (arr):       Array defining the image mask
    '''
    #Check if a mask already exists, if not enter digitising
    if writeMask!=None:
        try:
            myMask = Image.open(writeMask)
            myMask = np.array(myMask)
            print ('\nMask loaded. It is recommended that you check this ' 
                   'against the start and end of the sequence using the ' 
                   'self.checkMask() function of the TimeLapse object')
            return myMask
        except:
            print '\nMask file not found. Proceeding to manually digitise...'

    #Plot mask manually on the selected image
    fig=plt.gcf()
    fig.canvas.set_window_title('Click to create mask. Press enter to record' 
                                ' points.')
    imgplot = plt.imshow(img, origin='upper')
    imgplot.set_cmap('gray')
    x1 = plt.ginput(n=0, timeout=0, show_clicks=True, mouse_add=1, mouse_pop=3, 
                    mouse_stop=2)
    print '\n' + str(len(x1)) + ' points seeded'
    plt.show()
    
    #Close shape
    x1.append(x1[0])
    
    #Generate polygon
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for p in x1:
        ring.AddPoint(p[0],p[1])
    p=x1[0]
    ring.AddPoint(p[0],p[1])    
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
     
    #Rasterize polygon using PIL
    height = img.shape[0]
    width = img.shape[1]
    img1 = Image.new('L', (width,height), 0)
    draw=ImageDraw.Draw(img1)
    draw.polygon(x1, outline=1, fill=1)
    myMask=np.array(img1)
    
    #Write to .jpg file    
    if writeMask!=None:
        print '\nMask plotted: ' + writeMask
        try:
            img1.save(writeMask, 'jpg', quality=75)
        except:
            print '\nFailed to write file: ' + writeMask
        
    return myMask  


def readCalib(fileName, paramList):
    '''Function to find camera calibrations from a file given a list or 
    Matlab file containing the required parameters. Returns the parameters as a
    dictionary object.
    Compatible file structures:
    .txt file:   "RadialDistortion [k1,k2,k3...k8] 
                 TangentialDistortion [p1,p2]
                 IntrinsicMatrix [fx 0. 0.][s fy 0.][cx cy 1]
                 End"
    .mat file:   Camera calibration file output from the Matlab Camera 
                 Calibration App (available in the Computer Vision Systems 
                 toolbox).
    
    Variables
    fileName (str):         File directory for calibration file
    paramList (list):       List of strings denoting keywords to look for in 
                            calibration file
    
    Returns
    calib (list):           Calibration parameters denoted by keywords
    
    '''    
    #Load as text file if txt format
    if fileName[-3:] == 'txt':            
        #Open file
        try:
            myFile=open(fileName,'r')
        except:
            print '\nProblem opening calibration text file: ',fileName
            print 'No calibration parameters successfully read'
            return None
        
        #Read lines in file
        lines = []
        for line in myFile.readlines():
            lines.append(line[0:-1]) 
        
        #Set up a dictionary and input the calibration parameters 
        calib = {}
        for p in paramList:
            dataLines= lineSearch(lines, p)
            data = returnData(lines, dataLines)
            param = {}
            param[p] = data
            calib.update(param)        
        return calib
    
    #Load as matlab file if mat format
    elif fileName[-3:] == 'mat':            
        #Get the Matlab file as a dictionary
        mat = sio.loadmat(fileName)
           
        # Get desired keys from the dictionary
        calib = dict([(i, mat[i]) for i in paramList if i in mat])
        return calib
   
    #Incompatible file types     
    else:
        print ('\nYou have specified an incorrect calibration file type'
               '\nAcceptable file types are .txt and .mat.')


def lineSearch(lineList, search):
    '''Function to supplement the readCalib function. Given an input parameter 
    to search within the file, this will return the line numbers of the data.
    
    Variables
    lineList (list):        List of strings within a file line
    search (str):           Target keyword to search for
    
    Returns
    dataLines (list):       Line numbers with keyword match
    '''
    #Find line matching the parameter
    for i, line in enumerate(lineList):
        if search in line: 
            if len(search) == len(lineList[i]):
                match = i
    
    #Find lines containing the associated data        
    dataLines=[]
    atEnd=False
    match += 1
    while not(atEnd):
        if lineList[match][0].isupper() or lineList[match][0] == '_':
            atEnd=True
        else: 
            dataLines.append(match)
            match += 1
            
    return dataLines


def returnData(lines, data):
    '''Function to supplement the importCalibration function. Given the line 
    numbers of the parameter data (the ouput of the lineSearch function), this 
    will return the data.
    
    Variables
    lines (list):          Given line numbers to extract data from
    data (list):           Raw line data 
    
    Returns
    D (arr):               Extracted data
    '''    
    #Create empty list for output data
    D=[]
    
    for x in data:
        
        # Find the fields on each line
        lines[x] = lines[x].translate(None, '[]')
        fields = lines[x].split()
        d = []
        for f in fields:
            d.append(float(f))
            
        # Add the fields to the data list
        D.append(d)

    if len(D) > 1:
        D = np.array(D)
    
    return D


def readMatrixDistortion(path):
    '''Function to support the calibrate function. Returns the 
    intrinsic matrix and distortion parameters required for calibration from a
    given file.
    
    Variables
    path (str):         Directory of calibration file
    
    Returns
    intrMat (arr):      Intrinsic matrix as a 3x3 array, including focal 
                        length, principal point, and skew
    tanDis (arr):       Tangential distortion values (p1, p2)
    radDis (arr):       Radial distortion values (k1, k2... k6)
    '''   
    #Find the calibration parameters from the list
    ls = ['IntrinsicMatrix', 'RadialDistortion', 'TangentialDistortion']
    calibDict = readCalib(path, ls)
    
    #Stop if there is an issue in reading calibration file    
    if calibDict==None:
        return None   

    #Set calibration parameters in the correct format    
    intrMat = np.array(calibDict["IntrinsicMatrix"]) #fx,fy,s,cx,cy
    radDis = np.array(calibDict["RadialDistortion"]) # k1-k6
    tanDis = np.array(calibDict["TangentialDistortion"]) # p1,p2
   
    return intrMat, tanDis, radDis


def checkMatrix(matrix):
    '''Function to support the calibrate function. Checks and converts the 
    intrinsic matrix to the correct format for calibration with OpenCV.
    
    Variables
    matrix (arr):       Inputted matrix for checking
    
    Returns 
    mat (arr):          Validated matrix
    '''  
    # Transpose if zeros in matrix are not in correct places
    if matrix[2,0]!=0 and matrix[2,1]!=0 and matrix[0,2]==0 and matrix[1,2]==0:
        mat = matrix.transpose()
    else:
        mat = matrix
     
    # Set 0's and 1's in the correct locations
    it=np.array([0,1,1,0,2,0,2,1])     
    it.shape=(4,2)
    for i in range(4):
        x = it[i,0]
        y = it[i,1]
        mat[x,y]=0        
    mat[2,2]=1 

    return mat


def readImg(path, band='L', equal=True):
    '''Function to prepare an image by opening, equalising, converting to 
    either grayscale or a specified band, then returning a copy.

    Variables
    path (str):     Image file path directory.
    band (str):     Desired band output
                    'R': red band
                    'B': blue band
                    'G': green band
                    'L': grayscale (default).
                    
    Returns
    bw (arr):       Image array
    '''   
    # Open image file
    band=band.upper()
    im=Image.open(path)
    
    #Equalise histogram
    if equal is True:
        h = im.convert("L").histogram()
        lut = []
    
        for b in range(0, len(h), 256):
    
            #Step size
            step = reduce(operator.add, h[b:b+256]) / 255
    
            #Create equalization lookup table
            n = 0
            for i in range(256):
                lut.append(n / step)
                n = n + h[i+b]
        
        #Convert to grayscale
        gray = im.point(lut*im.layers)
    
    #Split bands if R, B or G is specified in inputs    
    if band=='R':
        gray,g,b=gray.split()
    elif band=='G':
        r,gray,b=gray.split() 
    elif band=='B':
        r,g,gray=gray.split() 
    else:
        gray = gray.convert('L')
    
    #Copy and return image    
    bw = np.array(gray).copy()
    
    return bw


def readGCPs(fileName):
    '''Function to read ground control points from a .txt file. The data in the
    file is referenced to under a header line. Data is appended by skipping the
    header line and finding the world and image coordinates from each line.
    
    Variables
    fileName (str):         File path directory for GCP file
    
    Returns
    world (arr):            World coordinates for GCPs
    image (arr):            Image coordinates for GCPs
    '''    
    # Open the file and read the first line (i.e. the header line)
    myFile=open(fileName,'r')  
    myFile.readline()

    #Iterate through lines and append to lists
    gcps= []
    count=2
    for line in myFile.readlines():  
        items=line.split('\t')
        gcp = []
        
        #Append values if they are valid
        for i in items:
            try:
                gcp.append(float(i)) 
            except ValueError:
                pass
        
        #Append points if there are 5 corresponding values
        if len(gcp)==5:    
            gcps.append(gcp)
        else:
            print ('\nGCP file line ' + str(count) + ' not passed forward')
        
        #Update counter        
        count=count+1
                  
    #Split the list into world and image coordinates
    gcparray = np.array(gcps)
    world, image = np.hsplit(gcparray,np.array([3]))
           
    return world, image

    
def writeCalibFile(intrMat, tanDis, radDis, fname):
    '''Write camera calibration data to .txt file, including camera matrix, and 
    radial and tangential distortion parameters. 

    Variables
    intrMat (arr):          Intrinsic camera matrix
    tanDis (arr):           Tangential distortion parameters
    radDis (arr):           Radial distortion parameters
    fname (str):            Directory to write file to
    '''         
    #Write camera calibration variables to text file
    f=open(fname,'w')                            
    f.write('RadialDistortion' + '\n' + str(radDis) + '\n' +
            'TangentialDistortion' + '\n' + str(tanDis) + '\n' +
            'IntrinsicMatrix' + '\n' + str(intrMat) + '\n' +
            'End')
            

def writeVeloFile(xyzvel, uvvel, homog, imn, fname):
    '''Function to write all velocity data from a given timeLapse sequence to 
    .csv file. Data is formatted as sequential columns containing the following
    information:
        Image pair 1 name
        Image pair 2 name
        Average xyz velocity
        Number of features tracked 
        Average pixel velocity
        Homography residual mean error (RMS)
        Signal-to-noise ratio
    
    Variables     
    xyzvel (list):          XYZ velocities
    uvvel (list):           Pixel velocities
    homog (list):           Homography (mtx, im0pts, im1pts, ptserr, homogerr)
    imn (list):             List of image names  
    fname (str)             Filename for output file. File destination can also 
                            specified
    '''        
    #Initialise file writing
    f=open(fname,'w')

    #Assign first image in pair
    fn1=imn[0]
    
    #Define column headers
    header=('Image 0, Image 1, Average xyz velocity, Features tracked, '
            'Average px velocity, Homography RMS Error, SNR')    
    f.write(header + '\n')

    #Iterate through timeLapse object
    for i in range(len(xyzvel)-1):
        
        #Re-define image0 for each iteration
        fn0=fn1
        
        #Get image1
        fn1=imn[i+1]
               
        #Get velocity data                     
        xyz = xyzvel[i]
        uv = uvvel[i]
        
        #Calculate average xyz and px velocities
        xyzvelav = sum(xyz)/len(xyz)
        uvvelav = sum(uv)/len(uv)
        #Write average xyzvel, number of features tracked, and uvvel
        f.write(str(fn0) + ','+ str(fn1) + ',' + str(xyzvelav) + ',' 
                + str(len(xyz)) + ',' + str(uvvelav) + ',')
                     
        #Get homography information if desired
        if homog is not None:
            hpt0 = homog[i][1][0]
            hpt1 = homog[i][1][1]
            hpt1corr = homog[i][1][2]
            herr = homog[i][3]
    
            #Get xyz homography errors                      
            xd=herr[1][0]
            yd=herr[1][1]
            
            #Get uv point positions                
            psx=hpt0[:,0,0]
            psy=hpt0[:,0,1]
            
            if hpt1corr is not None:
                pfx=hpt1corr[:,0,0]
                pfy=hpt1corr[:,0,1] 
            else:                   
                pfx=hpt1[:,0,0]
                pfy=hpt1[:,0,1]    
                
            #Determine uv point position difference
            pdx=pfx-psx
            pdy=pfy-psy
            
            #Calculate homography and homography error            
            homogdist=np.sqrt(pdx*pdx+pdy*pdy)
            errdist=np.sqrt(xd*xd+yd*yd)
            
            #Calculate mean homography and mean error 
            meanerrdist=np.mean(errdist)
            
            #Write pixel velocity, mean homog error, and SNR (pxvel/err)
            f.write(str(meanerrdist) + ','  + str(meanerrdist/uvvelav))

        else:
            #Write pixel velocity and NaN homography information
            f.write('NaN, NaN')
                         
        #Break line in output file
        f.write('\n')
            
    print '\nVelocity file written:' + fname        
        
   
def writeHomogFile(homog, imn, fname):
    '''Function to write all homography data from a given timeLapse sequence to 
    .csv file. Data is formatted as sequential columns containing the following 
    information:    
        Image pair 1 name
        Image pair 2 name
        Homography matrix (i.e. all values in the 3x3 matrix)
        Number of features tracked
        X mean displacement
        Y mean displacement
        X standard deviation
        Y standard deviation
        Mean error magnitude 
        Mean homographic displacement
        Signal-to-noise ratio
    
    Variables
    homog (list):           Homography (mtx, im0pts, im1pts, ptserr, homogerr)
    imn (list):             List of image names
    fname (str):            Directory for file to be written to
    '''
    #Initialise file writing
    f=open(fname,'w')
    
    #Write active directory to file
    fn1=imn[0]
    
    #Define column headers
    header=('Image 0,Image 1,"Homography Matrix[0,0]","[0,1]","[0,2]",'
            '"[1,0]","[1,1]","[1,2]","[2,0]","[2,1]","[2,2]",Features Tracked,'
            'xmean,ymean,xsd,ysd,Mean Error Magnitude,'
            'Mean Homographic displacement,Homography SNR')  
    
    f.write(header+'\n')

    #Iterate through timeLapse object
    for i in range(len(homog)-1):
        
        #Re-define image0 for each iteration
        fn0=fn1
        
        #Get image1
        fn0=imn[i+1]

        #Write image file names to file        
        f.write(fn0 + ',' + fn1 + ',')
        
        #Get homography info
        hmatrix = homog[i][0]               #Homography matrix
        hpt0 = homog[i][1][0]               #Seeded pts in im0
        hpt1 = homog[i][1][1]               #Tracked pts in im1
        hpt1corr = homog[i][1][2]           #Corrected pts im1
        herr = homog[i][3]                  #Homography error

        #Define output homography matrix
        if hmatrix is not None:
            hmatrix.shape=(9)
            for val in hmatrix:
                f.write(str(val) + ',')
                
        #Get xyz homography errors
        xd = herr[1][0]
        yd = herr[1][1] 
        
        #Get uv point positions
        psx = hpt0[:,0,0]
        psy = hpt0[:,0,1]
        
        if hpt1corr is None:
            pfx = hpt1[:,0,0]
            pfy = hpt1[:,0,1]
        else:
            pfx = hpt1corr[:,0,0]
            pfy = hpt1corr[:,0,1]
        
        #Determine uv point position difference
        pdx=pfx-psx
        pdy=pfy-psy
        
        #Calculate signal-to-noise ratio            
        errdist=np.sqrt(xd*xd+yd*yd)
        homogdist=np.sqrt(pdx*pdx+pdy*pdy)
        sn=errdist/homogdist
        
        #Determine number of points tracked in homography calculations
        f.write(str(len(hpt0)) + ',')
        
        #Define output homography matrix errors
        for val in herr[0]:
            f.write(str(val) + ',')
        
        #Compile all data for output file
        f.write(str(np.mean(errdist)) + ',' + str(np.mean(homogdist)) + ',' + 
                str(np.mean(sn)) + '\n')
        
    print '\nHomography file written' + fname


def writeAreaFile(areas, imn, dest):
    '''Write all area data (if it has been calculated) to the given files:
        
        Cumulative pixel extent:        Written as a single text file 
                                        containing delineated values of total 
                                        pixel area recorded for all images in 
                                        the sequence.
        Polygon pixel coordinates:      Written as a tab delimited text file 
                                        containing polygon xy coordinates.
        Cumulative xyz :                Written as a single text file 
                                        containing the total area of all the 
                                        polgons from each image.
        Polygon real coordinates:       Written as a tab delimited text file 
                                        containing polygon xyz coordinates
                                        
    All these file types are compatible with the importing tools (importPX, 
    importXYZ).
    
    Variables
    pxextent (list):                    Pixel extents
    pxpts (list):                       Pixel coordinates
    xyzarea (list):                     XYZ areas
    xyzpts (list):                      XYZ coordinates
    imn (list):                         Image names
    dest (str):                         Folder directory where output files 
                                        will be written to (NOT a specific 
                                        file).
    ''' 
    #Make directory if it does not exist
    if not os.path.exists(dest):
        os.makedirs(dest)
    
    #Get xyz and px info from input
    xyzarea = [item[0][0] for item in areas]
    xyzpts = [item[0][1] for item in areas]
    pxextent = [item[1][0] for item in areas]
    pxpts = [item[1][1] for item in areas]
    
    #Cumulative area of all pixel extents       
    if pxextent is not None:
        target = dest + 'px_sum.txt'
        f = open(target, 'w')
        f.write('Image \t Pixel extent \n')            
        for i in range(len(pxextent)):
            f.write(str(imn[i]) + '\t' + str(pxextent[i]) + '\n')

    #Pixel cooridnates of all pixel extents
    if pxpts is not None:
        target = dest + 'px_coords.txt'        
        f = open(target, 'w')
        polycount=1        
        for i in range(len(pxpts)):
            f.write('Img ' + str(imn[i]) + '\t')                
            for pol in pxpts[i]:
                f.write('Poly' + str(polycount) + '\t')                    
                for pts in pol:
                    if len(pts)==1:
                        f.write(str(pts[0][0]) + '\t' + str(pts[0][1]) + '\t')
                    elif len(pts)==2:
                        f.write(str(pts[0]) + '\t' + str(pts[1]) + '\t')
                polycount = polycount+1
            f.write('\n\n')
            polycount=1
            
    #Areas and cumulative areas of polygons
    if xyzarea is not None:
        target = dest + 'area_sum.txt'
        f = open(target, 'w')
        f.write('Image \t XYZ area \n')                       
        for i in range(len(xyzarea)):
            f.write(str(imn[i]) + '\t' + str(sum(xyzarea[i])) + '\n')

    #XYZ coordinates of polygons
    if xyzpts is not None:             
        target = dest + 'area_coords.txt'                   
        polycount=1  
        f = open(target, 'w')
        for i in range(len(xyzpts)):                
            f.write('Img ' + str(imn[i]) + '\t')
            for pol in xyzpts[i]:
                f.write('Poly' + str(polycount) + '\t')
                for pts in pol:
                    f.write(str(pts[0]) + '\t' + str(pts[1]) + '\t' + 
                            str(pts[2]) + '\t')
                polycount=polycount+1
            f.write('\n\n')
            polycount=1
                    

def writeLineFile(lines, imn, dest):
    '''Write all line data (if it has been calculated) to separate files.

        Pixel line length:              Written as a single text file 
                                        containing delineated values of total 
                                        pixel length recorded for all images in 
                                        the sequence.
        Line pixel coordinates:         Written as a tab delimited text file 
                                        containing line pixel coordinates.
        XYZ line length :               Written as a single text file 
                                        containing the total XYZ length for all 
                                        images in the sequence.
        Line XYZ coordinates:           Written as a tab delimited text file 
                                        containing line xyz coordinates 
    
    All these file types are compatible with the importing tools 
    (importLinePX, importLineXYZ)
    
    Variables
    pxline (list):                      Pixel line lengths
    pxpts (list):                       Pixel coordinates
    xyzline (list):                     XYZ line lengths
    xyzpts (list):                      XYZ coordinates
    imn (list):                         Image names
    dest (str):                         Folder directory where output files 
                                        will be written to (NOT a specific 
                                        file).      
    '''
    #Make directory if it does not exist
    if not os.path.exists(dest):
        os.makedirs(dest)

    #Get xyz and px info from input
    xyzline = [item[0][0] for item in lines]
    xyzpts = [item[0][1] for item in lines]
    pxline = [item[1][0] for item in lines]
    pxpts = [item[1][1] for item in lines]
        
    #Pixel line coordinates file generation             
    if pxpts is not None:            
        target = dest + 'line_pxcoords.txt'
        f = open(target, 'w')
        for i in range(len(pxpts)):
            f.write('Img ' + str(imn[i]) + '\t')                                   
            for pts in pxpts[i]:
                f.write(str(pts[0]) + '\t' + str(pts[1]) + '\t')    
            f.write('\n\n')

    #Pixel line length file generation            
    if pxline is not None:
        target = dest + 'line_pxlength.txt'
        f = open(target, 'w')
        f.write('Image \t Pixel length \n')            
        for i in range(len(pxline)):
            f.write(str(imn[i]) + '\t' + str(pxline[i]) + '\n')
    
    #Real line coordinates file generation
    if xyzpts is not None:
        target = dest + 'line_realcoords.txt'                    
        f = open(target, 'w')
        for i in range(len(xyzpts)):                
            f.write('Img ' + str(imn[i]) + '\t')
            for pts in xyzpts[i]:
                f.write(str(pts[0]) + '\t' + str(pts[1]) + '\t' + str(pts[2]) 
                + '\t')
            f.write('\n\n')
    
    #Real line length file generation            
    if xyzline is not None:
        target = dest + 'line_reallength.txt'
        f = open(target, 'w')
        f.write('Image \t XYZ length \n')
        for i in range(len(xyzline)):
            f.write(str(imn[i]) + '\t' + str(xyzline[i]) + '\n')


def writeVeloSHP(xyzvel, xyz0, imn, fileDirectory, projection=None):
    '''Write OGR real velocity points (from ALL images) to file in a .shp
    file type that is compatible with ESRI mapping software.
    
    Inputs
    xyzvel (list):              XYZ velocities
    xyz0 (list):                XYZ pt0
    imn (list):                 Image name
    fileDirectory (str):        Destination that shapefiles will be written to           
                                e.g. /python_workspace/Results/
    projection (int/str):       Coordinate projection that the shapefile will 
                                exist in. This can either be an ESPG number 
                                (expressed as an integer) or a well-known 
                                geographical coordinate system (expressed as a 
                                string). Well-known geographical coordinate 
                                systems are: 'WGS84', 'WGS72', NAD83' or 
                                'EPSG:n'
    ''' 
    #Make directory if it does not exist
    if not os.path.exists(fileDirectory):
        os.makedirs(fileDirectory)
        
    #Get driver and create shapeData in shp file directory              
    typ = 'ESRI Shapefile'
    driver = ogr.GetDriverByName(typ)
    if driver is None:
        raise IOError('%s Driver not available:\n' % typ)
        pass
        
    for i in range(len(xyzvel)): 
        
        #Get velocity, pt and image name for time step
        vel = xyzvel[i]
        pt0 = xyz0[i]            
        im = imn[i] 
        
        #Create file space            
        shp = fileDirectory + str(im) + '_vel.shp'
        if os.path.exists(shp):
            driver.DeleteDataSource(shp)
        ds = driver.CreateDataSource(shp)
        if ds is None:
            print 'Could not create file %s' %shp
        
        #Set projection
        if type(projection) is int:
            proj = osr.SpatialReference()
            proj.ImportFromEPSG(projection)
            layer = ds.CreateLayer(' ', proj, ogr.wkbPoint)
        elif type(projection) is str:
            proj = osr.SpatialReference()
            proj.SetWellKnownGeogCS(projection)
            layer = ds.CreateLayer(' ', proj, ogr.wkbPoint)
        else:
            layer = ds.CreateLayer(' ', None, ogr.wkbPoint)
   
        #Add attributes to layer
        layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))     #ID    
        layer.CreateField(ogr.FieldDefn('velocity', ogr.OFTReal))  #Velo
        
        #Get xy coordinates
        x0 = pt0[:,0]
        y0 = pt0[:,1]
        
        #Create point features with data attributes in layer           
        for v,x,y in zip(vel, x0, y0):
            count=1
        
            #Create feature    
            feature = ogr.Feature(layer.GetLayerDefn())
        
            #Create feature attributes    
            feature.SetField('id', count)
            feature.SetField('velocity', v)
        
            #Create feature location
            wkt = "POINT(%f %f)" %  (float(x) , float(y))
            point = ogr.CreateGeometryFromWkt(wkt)
            feature.SetGeometry(point)
            layer.CreateFeature(feature)
        
            #Free up data space
            feature.Destroy()                       
            count=count+1

        #Free up data space                          
        ds.Destroy()
        

def writeAreaSHP(xyzpts, imn, fileDirectory, projection=None):
    '''Write OGR real polygon areas (from ALL images) to file in a .shp
    file type that is compatible with ESRI mapping software.
    
    Inputs
    xyzpts (list):              XYZ coordinates for polygons
    imn (list):                 Iname names
    fileDirectory (str):        Destination that shapefiles will be written to           
                                e.g. /python_workspace/Results/
    projection (int/str):       Coordinate projection that the shapefile will 
                                exist in. This can either be an ESPG number 
                                (expressed as an integer) or a well-known 
                                geographical coordinate system (expressed as a 
                                string). Well-known geographical coordinate 
                                systems are: 'WGS84', 'WGS72', NAD83' or 
                                'EPSG:n'
    ''' 
    #Make directory if it does not exist
    if not os.path.exists(fileDirectory):
        os.makedirs(fileDirectory)
        
    #Get driver and create shapeData in shp file directory        
    typ = 'ESRI Shapefile'        
    driver = ogr.GetDriverByName(typ)
    if driver is None:
        raise IOError('%s Driver not available:\n' % typ)
        pass
        
    for i in range(len(xyzpts)): 
        
        #Get polygon coordinates and image name for each time step
        polys = xyzpts[i]          
        im = imn[i] 
                      
        #Create datasource in shapefile
        shp = fileDirectory + str(im) + '_area.shp'
        
        if os.path.exists(shp):
            driver.DeleteDataSource(shp)
        ds = driver.CreateDataSource(shp)
        if ds is None:
            print 'Could not create file %s' %shp
    
        if type(projection) is int:
            proj = osr.SpatialReference()
            proj.ImportFromEPSG(projection)
            layer = ds.CreateLayer(' ', proj, ogr.wkbPolygon)
        elif type(projection) is str:
            proj = osr.SpatialReference()
            proj.SetWellKnownGeogCS(projection)
            layer = ds.CreateLayer(' ', proj, ogr.wkbPolygon)
        else:
            layer = ds.CreateLayer(' ', None, ogr.wkbPolygon)
    
        #Add attributes
        layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))
        layer.CreateField(ogr.FieldDefn('area', ogr.OFTReal))
        
        #Get ogr polygons from xyz areal data at given image 
        ogrpolys = []        
        for shape in polys:
            ring = ogr.Geometry(ogr.wkbLinearRing)
            for pt in shape:
                if np.isnan(pt[0]) == False:                   
                    ring.AddPoint(pt[0],pt[1],pt[2])
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            ogrpolys.append(poly)
            
        polycount=1

        #Create feature            
        for p in ogrpolys:
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(p)
            feature.SetField('id', polycount)
            feature.SetField('area', p.Area())
            layer.CreateFeature(feature)
            feature.Destroy()                
            polycount=polycount+1
        
        ds.Destroy()
        
        
def writeLineSHP(xyzpts, imn, fileDirectory, projection=None):
    '''Write OGR real line features (from ALL images) to file in a .shp
    file type that is compatible with ESRI mapping software.
    
    Inputs
    xyzpts (list):              XYZ coordinates for lines
    imn (list):                 Image names
    fileDirectory (str):        Destination that shapefiles will be written to           
                                e.g. /python_workspace/Results/
    projection (int/str):       Coordinate projection that the shapefile will 
                                exist in. This can either be an ESPG number 
                                (expressed as an integer) or a well-known 
                                geographical coordinate system (expressed as a 
                                string). Well-known geographical coordinate 
                                systems are: 'WGS84', 'WGS72', NAD83' or 
                                'EPSG:n'
    ''' 
    #Make directory if it does not exist
    if not os.path.exists(fileDirectory):
        os.makedirs(fileDirectory)
        
    #Get driver and create shapeData in shp file directory        
    typ = 'ESRI Shapefile'        
    driver = ogr.GetDriverByName(typ)
    if driver is None:
        raise IOError('%s Driver not available:\n' % typ)
        pass
       
    for i in range(len(xyzpts)):
        
        #Get polygon coordinates and image name for each time step
        rline = xyzpts[i]  
        im = imn[i]

        #Create datasource in shapefile
        shp = fileDirectory + str(im) + '_line.shp'
        
        if os.path.exists(shp):
            driver.DeleteDataSource(shp)
        ds = driver.CreateDataSource(shp)
        if ds is None:
            print 'Could not create file %s' %shp
    
        if type(projection) is int:
            proj = osr.SpatialReference()
            proj.ImportFromEPSG(projection)
            layer = ds.CreateLayer(' ', proj, ogr.wkbLineString)
        elif type(projection) is str:
            proj = osr.SpatialReference()
            proj.SetWellKnownGeogCS(projection)
            layer = ds.CreateLayer(' ', proj, ogr.wkbLineString)
        else:
            layer = ds.CreateLayer(' ', None, ogr.wkbLineString)
        
        #Add attributes
        layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))
        layer.CreateField(ogr.FieldDefn('length', ogr.OFTReal))

        lcount=1
        
        line = ogr.Geometry(ogr.wkbLineString)   
        for p in rline:
            line.AddPoint(p[0],p[1])
        
        #Create feature            
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(line)
        feature.SetField('id', lcount)
        feature.SetField('length', line.Length())
        layer.CreateFeature(feature)
        feature.Destroy() 
        lcount=lcount+1
        
        ds.Destroy()


def importAreaData(xyzfile, pxfile):
    '''Import xyz and px data from text files.
    
    Variables
    xyzfile (str):      File directory to xyz coordinates
    pxfile (str):       File directory to uv coordinates
            
    Returns
    rpoly (list):       Real xyz coordinates of detected areas
    rarea (list):       Real-world surface areas
    pxpoly (list):      XY pixel coordinates of detected areas
    pxarea (list):      Pixel areas
    '''
    #Get real-world coordinates and areas       
    rpoly, rarea = importAreaXYZ(xyzfile)

    #Get pixel coordinates and areas    
    pxpoly, pxarea = importAreaPX(pxfile)

    #Return all area data   
    return rpoly, rarea, pxpoly, pxarea


def importLineData(xyzfile, pxfile):
    '''Import xyz and px data from text files.
    
    Variables
    xyzfile (str):       File directory to xyz coordinates
    pxfile (str):        File directory to uv coordinates
            
    Returns
    rline:        Real xyz coordinates of detected lines
    rlength:      Real-world surface distances
    pxline:       XY pixel coordinates of detected lines
    pxlength:     Pixel distances
    '''
    #Get real-world coordinates and distances
    rline, rlength = importLineXYZ(xyzfile)
    
    #Get pixel coordinates and distances
    pxline, pxlength = importLinePX(pxfile)
    
    #Return all line data
    return rline, rlength, pxline, pxlength
        
        
def importAreaXYZ(fname):
    '''Import xyz polygon data from text file and compute areas.
    
    Variables    
    fname (str):         Path to the text file containing the xyz coordinate 
                         data

    Returns
    xyz (list):         XYZ coordinates for polygons from images
    area (list):        XYZ areas for polygons from images
    '''
    #Import polygon coordinates from text file
    f=file(fname,'r')                                
    alllines=[]
    for line in f.readlines():
        if len(line) >= 6:
            alllines.append(line)  #Read lines in file             
    print '\nDetected xyz coordinates from ' + str(len(alllines)) + ' images'
    f.close()
    
    #Set up xyz object
    xyz=[] 
    area=[]
    count=0

    #Extract polygon data as strings
    for line in alllines:
        img=[]
        strpolys=[] 
        ogrpolys=[]            
        temp=line.split('Pol')                                    
        for i in temp:
            if len(i) >=10:
                strpolys.append(i)
        count=count+1
        print 'Detected '+str(len(strpolys))+' polygons in image '+(str(count))                
        
        #Extract polygon values from strings
        for strp in strpolys:
            pts = strp.split('\t')
            coords=[]
            for p in pts:
                try:
                    coords.append(float(p))
                except ValueError:
                    pass
            struc = len(coords)/3
            polygon = np.array(coords).reshape(struc, 3)
            img.append(polygon)
        
        #Create geometries from polgon values using ogr               
        for shape in img:
            ring = ogr.Geometry(ogr.wkbLinearRing)
            for pt in shape:
                if np.isnan(pt[0]) == False:                   
                    ring.AddPoint(pt[0],pt[1],pt[2])
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            ogrpolys.append(poly.Area())  
            
        xyz.append(img)
        area.append(ogrpolys)
    
    #Return polygon and area data
    return xyz, area
   

def importAreaPX(fname):
    '''Import pixel polygon data from text file and compute pixel extents.
    
    Variables    
    fname (str):         Path to the text file containing the UV coordinate 
                         data

    Returns
    uv (list):           UV coordinates for polygons 
    extent (list):       Pixel areas for polygons          
    '''
    #Import px polygon coordinates from text file
    f=file(fname, 'r')
    alllines=[]
    for line in f.readlines():
        if len(line) >=6:
            alllines.append(line)
    print '\nDetected px coordinates from ' + str(len(alllines)) + ' images'
    f.close()
    
    #Set up xyz object
    uv=[]
    extent=[]
    count=0

    #Extract polygon data as strings
    for line in alllines:
        img=[]
        strpolys=[]  
        ogrpolys=[]         
        temp=line.split('Pol')                                    
        for i in temp:
            if len(i) >=10:
                strpolys.append(i)

        count=count+1
        print ('Detected ' + str(len(strpolys)) + ' polygons in image ' 
               + (str(count)))                
        
        #Extract polygon values from strings
        for strp in strpolys:
            pts = strp.split('\t')
            coords=[]
            for p in pts:
                try:
                    coords.append(float(p))
                except ValueError:
                    pass
            struc = len(coords)/2
            polygon = np.array(coords).reshape(struc, 2)
            img.append(polygon)
        
        #Create geometries from polgon values using ogr               
        for shape in img:
            ring = ogr.Geometry(ogr.wkbLinearRing)
            for pt in shape:
                if np.isnan(pt[0]) == False:                   
                    ring.AddPoint(pt[0],pt[1])
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            ogrpolys.append(poly.Area())  
        
        uv.append(img)
        extent.append(ogrpolys)
    
    return uv, extent
     
     
def importLineXYZ(fname):
    '''Import XYZ line data from text file and compute line lengths.
    
    Variables    
    fname (str):         Path to the text file containing the XYZ coordinate 
                         data

    Returns
    xyz (list):          XYZ coordinates for lines from images  
    lines (list):        Line lengths
    '''
    #Read file and detect number of images based on number of lines
    f=file(fname,'r')      
    alllines=[]
    for line in f.readlines():
        if len(line) >= 6:
            alllines.append(line)  #Read lines in file             
    print '\nDetected coordinates from ' + str(len(alllines)) + ' images'
    f.close() 
    
    #Extract strings from lines         
    xyz=[] 
    for line in alllines:
        vals = line.split('\t')
        
        coords=[]
        raw=[]
                      
        #Extract coordinate values from strings
        for v in vals:
            try:
                a=float(v)
                raw.append(a)
            except ValueError:
                pass
            
        #Restructure coordinates based into 3D points
        struc = len(raw)/3            
        coords = np.array(raw).reshape(struc, 3)
        xyz.append(coords)
     
    #Create OGR line object
    lines=[]
    for line in xyz:        
        length = ogr.Geometry(ogr.wkbLineString)   
        for p in line:
            length.AddPoint(p[0],p[1])
        lines.append(length)
    
    return xyz, lines
   

def importLinePX(fname):
    '''Get px line and length data from multiple text files and import
    into a Line class object.
    
    Variables    
    fname (str):         Path to the text file containing the UV coordinate 
                         data

    Returns
    uv (list):           UV coordinates for lines from images  
    lines (list):        Line lengths
     '''
    #Read file and detect number of images based on number of lines
    f=file(fname,'r')      
    alllines=[]
    for line in f.readlines():
        if len(line) >= 6:
            alllines.append(line)  #Read lines in file             
    print '\nDetected coordinates from ' + str(len(alllines)) + ' images'
    f.close()
    
    #Extract strings from lines   
    uv=[]        
    for line in alllines:
        vals = line.split('\t')        
        coords=[]
        raw=[]
                      
        #Extract coordinate values from strings
        for v in vals:
            try:
                a=float(v)
                raw.append(a)
            except ValueError:
                pass
            
        #Restructure coordinates based on 2D dimension
        struc = len(raw)/2            
        coords = np.array(raw).reshape(struc, 2)
        uv.append(coords)
       
    #Create OGR line object
    lines = []
    for line in uv:        
        length = ogr.Geometry(ogr.wkbLineString)   
        for p in line:
            length.AddPoint(p[0],p[1])
        lines.append(length)
    
    return uv, lines

    
#------------------------------------------------------------------------------

#if __name__ == "__main__":   
#    print '\nProgram finished'

#------------------------------------------------------------------------------   
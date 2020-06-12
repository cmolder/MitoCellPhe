#@ ImagePlus imp
#@ File(label="Pre-processor path:", value = "", required=False) preprocessor_path
#@ File(label="Post-processing path:", required=False) postprocessor_path
#@ String(label = "Thresholding Op:", value="otsu", choices={"huang", "ij1", "intermodes", "isoData", "li", "maxEntropy", "maxLikelihood", "mean", "minError", "minimum", "moments", "otsu", "percentile", "renyiEntropy", "rosin", "shanbhag", "triangle", "yen"}) threshold_method
#@ Boolean(label="Use ridge detection (2D only):", value=False) use_ridge_detection
#@ BigInteger(label="High contrast:", value=75, required=False) rd_max
#@ BigInteger(label="Low contrast:", value=5, required=False) rd_min
#@ BigInteger(label="Line width:", value=1, required=False) rd_width
#@ BigInteger(label="Line length:", value=3, required=False) rd_length
#@ String(label="User comment: ", value="") user_comment

#@ OpService ops
#@ ScriptService scripts
#@ UIService ui

#@output String image_title
#@output String preprocessor_path
#@output String postprocessor_path
#@output String thresholding_op
#@output Boolean use_ridge_detection

#@output int high_contrast
#@output int low_contrast

#@output int line_width
#@output BigDecimal mitocondrial_footprint

#@output BigDecimal branch_len_mean
#@output BigDecimal branch_len_med
#@output BigDecimal branch_len_stdevp

#@output BigDecimal summed_branch_lens_mean
#@output BigDecimal summed_branch_lens_med
#@output BigDecimal summed_branch_lens_stdevp

#@output BigDecimal network_branches_mean
#@output BigDecimal network_branches_med
#@output BigDecimal network_branches_stdevp


from math import sqrt
from ij import IJ
from ij import ImagePlus
from ij import WindowManager
from ij.gui import ImageRoi
from ij.gui import Overlay
from ij.measure import ResultsTable, Measurements
from ij.plugin import Duplicator
from ij.process import ImageStatistics

from net.imglib2.img.display.imagej import ImageJFunctions
from net.imglib2.type.numeric.integer import UnsignedByteType

from sc.fiji.analyzeSkeleton import AnalyzeSkeleton_

# from ij3d import Image3DUniverse

from org.scijava.vecmath import Point3f
from org.scijava.vecmath import Color3f

# Helper functions..............................................................
def ridge_detect(imp, rd_max, rd_min, rd_width, rd_length):
    title = imp.getTitle()
    IJ.run(imp, "8-bit", "");
    IJ.run(imp, "Ridge Detection", "line_width=%s high_contrast=%s low_contrast=%s make_binary method_for_overlap_resolution=NONE minimum_line_length=%s maximum=0" % (rd_width, rd_max, rd_min, rd_length))
    IJ.run(imp, "Remove Overlay", "")
    skel = WindowManager.getImage(title + " Detected segments")
    IJ.run(skel, "Skeletonize (2D/3D)", "")
    skel.hide()
    return(skel)

def average(num_list):
    return sum(num_list)/len(num_list)

def median(num_list):
    sorted_list = sorted(num_list)
    length      = len(num_list)
    index = (length - 1) // 2

    if (length % 2):
        return sorted_list[index]
    else:
        return (sorted_list[index] + sorted_list[index + 1])/2.0

def pstdev(num_list):
    var = 0 # Variance
    avg = average(num_list)
    for num in num_list:
        var = var + (num - avg)**2
    var = var / len(num_list)
    return sqrt(var)


# The run function..............................................................
def run():

    # output_parameters = {"image title" : "",
    # "preprocessor path" : float,
    # "post processor path" : float,
    # "thresholding op" : float,
    # "use ridge detection" : bool,
    # "high contrast" : int,
    # "low contrast" : int,
    # "line width" : int,
    # "minimum line length" : int,
    # "mitochondrial footprint" : float,
    # "branch length mean" : float,
    # "branch length median" : float,
    # "branch length stdevp" : float,
    # "summed branch lengths mean" : float,
    # "summed branch lengths median" : float,
    # "summed branch lengths stdevp" : float,
    # "network branches mean" : float,
    # "network branches median" : float,
    # "network branches stdevp" : float}
    output_parameters = {}

    output_order = ["image title",
    "preprocessor path",
    "post processor path",
    "thresholding op",
    "use ridge detection",
    "high contrast",
    "low contrast",
    "line width",
    "minimum line length",
    "mitochondrial footprint",
    "branch length mean",
    "branch length median",
    "branch length stdevp",
    "summed branch lengths mean",
    "summed branch lengths median",
    "summed branch lengths stdevp",
    "network branches mean",
    "network branches median",
    "network branches stdevp"]

    # Perform any preprocessing steps...
    imp = IJ.getImage() # ImageJ is not detecting imp, so maybe this will fix it.
    if preprocessor_path != None:
        if preprocessor_path.exists():
            IJ.log("Preprocessor path found! Preprocessing image...")
            preprocessor_thread = scripts.run(preprocessor_path, True)
            preprocessor_thread.get()
            imp = WindowManager.getCurrentImage()
    else:
        pass

    # Store all of the analysis parameters in the table
    if preprocessor_path == None:
        preprocessor_str = ""
    else:
        preprocessor_str = preprocessor_path.getCanonicalPath()
    if postprocessor_path == None:
        postprocessor_str = ""
    else:
        postprocessor_str = preprocessor_path.getCanonicalPath()

    output_parameters["preprocessor path"] = preprocessor_str
    output_parameters["post processor path"] = postprocessor_str
    output_parameters["thresholding op"] = threshold_method
    output_parameters["use ridge detection"] = str(use_ridge_detection)
    output_parameters["high contrast"] = rd_max
    output_parameters["low contrast"] = rd_min
    output_parameters["line width"] = rd_width
    output_parameters["minimum line length"] = rd_length

    # Create and ImgPlus copy of the ImagePlus for thresholding with ops...
    IJ.log("Determining threshold level...")

    imp_title = imp.getTitle()
    slices = imp.getNSlices()
    frames = imp.getNFrames()
    output_parameters["image title"] = imp_title
    imp_calibration = imp.getCalibration()
    imp_channel = Duplicator().run(imp, imp.getChannel(), imp.getChannel(), 1, slices, 1, frames)
    img = ImageJFunctions.wrap(imp_channel)

    # Determine the threshold value if not manual...
    binary_img = ops.run("threshold.%s"%threshold_method, img)
    binary = ImageJFunctions.wrap(binary_img, 'binary')
    binary.setCalibration(imp_calibration)
    binary.setDimensions(1, slices, 1)

    # Get the total_area
    if binary.getNSlices() == 1:
        area = binary.getStatistics(Measurements.AREA).area
        area_fraction = binary.getStatistics(Measurements.AREA_FRACTION).areaFraction
        output_parameters["mitochondrial footprint"] =  area * area_fraction / 100.0
    else:
        mito_footprint = 0.0
        for slice in range(binary.getNSlices()):
            	binary.setSliceWithoutUpdate(slice)
                area = binary.getStatistics(Measurements.AREA).area
                area_fraction = binary.getStatistics(Measurements.AREA_FRACTION).areaFraction
                mito_footprint += area * area_fraction / 100.0
        output_parameters["mitochondrial footprint"] = mito_footprint * imp_calibration.pixelDepth

    # Generate skeleton from masked binary ...
    # Generate ridges first if using Ridge Detection
    if use_ridge_detection and (imp.getNSlices() == 1):
        skeleton = ridge_detect(imp, rd_max, rd_min, rd_width, rd_length)
    else:
        skeleton = Duplicator().run(binary)
        IJ.run(skeleton, "Skeletonize (2D/3D)", "")

    # Analyze the skeleton...
    IJ.log("Setting up skeleton analysis...")
    skel = AnalyzeSkeleton_()
    skel.setup("", skeleton)
    IJ.log("Analyzing skeleton...")
    skel_result = skel.run()

    IJ.log("Computing graph based parameters...")
    branch_lengths = []
    summed_lengths = []
    graphs = skel_result.getGraph()

    for graph in graphs:
        summed_length = 0.0
        edges = graph.getEdges()
        for edge in edges:
            length = edge.getLength()
            branch_lengths.append(length)
            summed_length += length
        summed_lengths.append(summed_length)

    output_parameters["branch length mean"]   = average(branch_lengths)
    output_parameters["branch length median"] = median(branch_lengths)
    output_parameters["branch length stdevp"] = pstdev(branch_lengths)

    output_parameters["summed branch lengths mean"]   = average(summed_lengths)
    output_parameters["summed branch lengths median"] = median(summed_lengths)
    output_parameters["summed branch lengths stdevp"] = pstdev(summed_lengths)

    branches = list(skel_result.getBranches())
    output_parameters["network branches mean"]   = average(branches)
    output_parameters["network branches median"] = median(branches)
    output_parameters["network branches stdevp"] = pstdev(branches)

    # Create/append results to a ResultsTable...
    IJ.log("Display results...")
    if "Mito Morphology" in list(WindowManager.getNonImageTitles()):
        rt = WindowManager.getWindow("Mito Morphology").getTextPanel().getOrCreateResultsTable()
    else:
        rt = ResultsTable()

    rt.incrementCounter()
    for key in output_order:
        rt.addValue(key, str(output_parameters[key]))

    # Add user comments intelligently
    if user_comment != None and user_comment != "":
        if "=" in user_comment:
            comments = user_comment.split(",")
            for comment in comments:
                rt.addValue(comment.split("=")[0], comment.split("=")[1])
        else:
            rt.addValue("Comment", user_comment)

    # rt.show("Mito Morphology") # Do not show in headless mode

	# Create overlays on the original ImagePlus and display them if 2D...
    if imp.getNSlices() == 1:
        IJ.log("Generate overlays...")
        IJ.run(skeleton, "Green", "")
        IJ.run(binary, "Magenta", "")

        skeleton_ROI = ImageRoi(0,0,skeleton.getProcessor())
        skeleton_ROI.setZeroTransparent(True)
        skeleton_ROI.setOpacity(1.0)
        binary_ROI = ImageRoi(0,0,binary.getProcessor())
        binary_ROI.setZeroTransparent(True)
        binary_ROI.setOpacity(0.25)

        overlay = Overlay()
        overlay.add(binary_ROI)
        overlay.add(skeleton_ROI)

        imp.setOverlay(overlay)
        imp.updateAndDraw()

    '''
    # Generate a 3D model if a stack
    if imp.getNSlices() > 1:

        univ = Image3DUniverse()
        univ.show()

        pixelWidth = imp_calibration.pixelWidth
        pixelHeight = imp_calibration.pixelHeight
        pixelDepth = imp_calibration.pixelDepth

        # Add end points in yellow
        end_points = skel_result.getListOfEndPoints()
        end_point_list = []
        for p in end_points:
            end_point_list.append(Point3f(p.x * pixelWidth, p.y * pixelHeight, p.z * pixelDepth))
        univ.addIcospheres(end_point_list, Color3f(255.0, 255.0, 0.0), 2, 1*pixelDepth, "endpoints")

        # Add junctions in magenta
        junctions = skel_result.getListOfJunctionVoxels()
        junction_list = []
        for p in junctions:
            junction_list.append(Point3f(p.x * pixelWidth, p.y * pixelHeight, p.z * pixelDepth))
        univ.addIcospheres(junction_list, Color3f(255.0, 0.0, 255.0), 2, 1*pixelDepth, "junctions")

        # Add the lines in green
        graphs = skel_result.getGraph()
        for graph in range(len(graphs)):
            edges = graphs[graph].getEdges()
            for edge in range(len(edges)):
                branch_points = []
                for p in edges[edge].getSlabs():
                    branch_points.append(Point3f(p.x * pixelWidth, p.y * pixelHeight, p.z * pixelDepth))
                univ.addLineMesh(branch_points, Color3f(0.0, 255.0, 0.0), "branch-%s-%s"%(graph, edge), True)

        # Add the surface
        univ.addMesh(binary)
        univ.getContent("binary").setTransparency(0.5)
    '''

    # Perform any postprocessing steps...
    if postprocessor_path != None:
        if postprocessor_path.exists():
            IJ.log("Postprocessor path found! Running postprocessing...")
            postprocessor_thread = scripts.run(postprocessor_path, True)
            postprocessor_thread.get()
    else:
        pass

    IJ.log("Done analysis!")

    return output_parameters

# Run the script...
if (__name__=="__main__") or (__name__=="__builtin__"):
    outputs = run()

    # Collect all the outputs in their relevant titles.
    image_title         = outputs["image title"]
    preprocessor_path   = outputs["preprocessor path"]
    postprocessor_path  = outputs["post processor path"]
    thresholding_op     = outputs["thresholding op"]
    use_ridge_detection = outputs["use ridge detection"]

    high_contrast = outputs["high contrast"]
    low_contrast  = outputs["low contrast"]

    line_width             = outputs["line width"]
    min_line_length        = outputs["minimum line length"]
    mitocondrial_footprint = outputs["mitochondrial footprint"]

    branch_len_mean   = outputs["branch length mean"]
    branch_len_med    = outputs["branch length median"]
    branch_len_stdevp = outputs["branch length stdevp"]

    summed_branch_lens_mean   = outputs["summed branch lengths mean"]
    summed_branch_lens_med    = outputs["summed branch lengths median"]
    summed_branch_lens_stdevp = outputs["summed branch lengths stdevp"]

    network_branches_mean   = outputs["network branches mean"]
    network_branches_med    = outputs["network branches median"]
    network_branches_stdevp = outputs["network branches stdevp"]

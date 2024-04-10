# downloads every edgelist file on s3 into a local temp directory using `boto3`
# %%
"""graph_stats : functionality for computing statistics on ndmg directories.
"""
import warnings
from collections import namedtuple
from pathlib import Path
import re

# from math import sqrt
import numpy as np

# from scipy.stats import rankdata
from matplotlib import pyplot as plt

# from graspy.utils import pass_to_ranks
from graspologic.utils import pass_to_ranks

# from graspy.plot import heatmap
from graspologic.plot import heatmap

# from graphutils.graph_io import NdmgGraphs
# from graphutils.utils import replace_doc, nearest_square
import shutil
import os
from functools import reduce
import networkx as nx
from graspologic.utils import import_edgelist

# from graspy.utils import import_edgelist
# from graphutils.utils import is_graph
# from graphutils.utils import filter_graph_files
# from graphutils.s3_utils import (
#     get_matching_s3_objects,
#     get_credentials,
#     s3_download_graph,
#     parse_path,
# )
from sklearn.metrics import euclidean_distances
from sklearn.utils import check_X_y
from collections import OrderedDict


def get_credentials():
    """
    Get aws credentials from either environment or aws config.

    Returns
    -------
    tuple
         aws credentials.

    Raises
    ------
    AttributeError
        Occurs if credentials don't exist.
    """
    try:
        config = ConfigParser()
        config.read(os.getenv("HOME") + "/.aws/credentials")
        return (
            config.get("default", "aws_access_key_id"),
            config.get("default", "aws_secret_access_key"),
        )
    except:
        ACCESS = os.getenv("AWS_ACCESS_KEY_ID")
        SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not ACCESS and SECRET:
        raise AttributeError("No AWS credentials found.")
    return (ACCESS, SECRET)


def parse_path(s3_datapath):
    """
    Return bucket and prefix from full s3 path.

    Parameters
    ----------
    s3_datapath : str
        path to a bucket.
        Should be of the form s3://bucket/prefix/.

    Returns
    -------
    tuple
        bucket and prefix.
    """
    bucket_path = str(s3_datapath).split("//")[1]
    parts = bucket_path.split("/")
    bucket = parts[0]
    prefix = "/".join(parts[1:4])
    return bucket, prefix


def s3_client(service="s3"):
    """
    create an s3 client.

    Parameters
    ----------
    service : str
        Type of service.

    Returns
    -------
    boto3.client
        client with proper credentials.
    """

    ACCESS, SECRET = get_credentials()
    return boto3.client(service, aws_access_key_id=ACCESS, aws_secret_access_key=SECRET)


def get_matching_s3_objects(bucket, prefix="", suffix=""):
    """
    Generate objects in an S3 bucket.

    Parameters
    ----------
    bucket : str
        Name of the s3 bucket.
    prefix : str, optional
        Only fetch objects whose key starts with this prefix, by default ''
    suffix : str, optional
        Only fetch objects whose keys end with this suffix, by default ''
    """
    s3 = s3_client()
    kwargs = {"Bucket": bucket}

    # If the prefix is a single string (not a tuple of strings), we can
    # do the filtering directly in the S3 API.
    if isinstance(prefix, str):
        kwargs["Prefix"] = prefix

    while True:

        # The S3 API response is a large blob of metadata.
        # 'Contents' contains information about the listed objects.
        resp = s3.list_objects_v2(**kwargs)

        try:
            contents = resp["Contents"]
        except KeyError:
            print("No contents found.")
            return

        for obj in contents:
            key = obj["Key"]
            if key.startswith(prefix) and key.endswith(suffix):
                yield key

        # The S3 API is paginated, returning up to 1000 keys at a time.
        # Pass the continuation token into the next response, until we
        # reach the final page (when this field is missing).
        try:
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
        except KeyError:
            break


def s3_download_graph(bucket, prefix, local):
    """
    Given an s3 directory, copies in that directory to local.

    Parameters
    ----------
    bucket : str
        s3 bucket name.
    prefix :
        location of s3 object.
    local : str
        s3 object download location.
    """
    parent = Path(local).parent
    if not parent.is_dir():
        parent.mkdir(parents=True, exist_ok=True)
    s3 = s3_client()
    s3.download_file(bucket, prefix, local)


def replace_doc(value):
    """
    Decorator for changing docstring of a function.

    Parameters
    ----------
    value : str
        docstring to change to.

    Returns
    -------
    func
        wrapper function.
    """

    def _doc(func):
        func.__doc__ = value
        return func

    return _doc


KEYWORDS = ["sub", "ses"]


def is_graph(filename, atlas="", suffix=""):
    """
    Check if `filename` is a ndmg graph file.

    Parameters
    ----------
    filename : str or Path
        location of the file.

    Returns
    -------
    bool
        True if the file has the ndmg naming convention, else False.
    """

    if atlas:
        atlas = atlas.lower()
        KEYWORDS.append(atlas)

    if suffix:
        if not suffix.startswith("."):
            suffix = "." + suffix

    correct_suffix = Path(filename).suffix == suffix
    correct_filename = all(i in str(filename) for i in KEYWORDS)
    return correct_suffix and correct_filename


def filter_graph_files(file_list, return_bool=False, **kwargs):
    """
    Generator.
    Check if each file in `file_list` is a ndmg edgelist,
    yield it if it is.

    Parameters
    ----------
    return_bool : bool
        if True, return a boolearn that says whether graph files exist in the directory.
    file_list : iterator
        iterator of inputs to the `is_graph` function.
    """
    if return_bool:
        has_graphs = any(is_graph(x, **kwargs) for x in file_list)
        return has_graphs
    for filename in file_list:
        if is_graph(filename, **kwargs):
            yield (filename)


def discr_stat(
    X, Y, dissimilarity="euclidean", remove_isolates=True, return_rdfs=False
):
    """
    Computes the discriminability statistic.
    Parameters
    ----------
    X : array, shape (n_samples, n_features) or (n_samples, n_samples)
    Input data. If dissimilarity=='precomputed', the input should be the dissimilarity
    matrix.
    Y : 1d-array, shape (n_samples)
    Input labels.
    dissimilarity : str, {"euclidean" (default), "precomputed"}
    Dissimilarity measure to use:
    - 'euclidean':
    Pairwise Euclidean distances between points in the dataset.
    - 'precomputed':
    Pre-computed dissimilarities.
    remove_isolates : bool, optional, default=True
    Whether to remove data that have single label.
    return_rdfs : bool, optional, default=False
    Whether to return rdf for all data points.
    Returns
    -------
    stat : float
    Discriminability statistic.
    rdfs : array, shape (n_samples, max{len(id)})
    Rdfs for each sample. Only returned if ``return_rdfs==True``.
    """
    check_X_y(X, Y, accept_sparse=True)
    uniques, counts = np.unique(Y, return_counts=True)
    if (counts != 1).sum() <= 1:
        msg = "You have passed a vector containing only a single unique sample id."
        raise ValueError(msg)
    if remove_isolates:
        idx = np.isin(Y, uniques[counts != 1])
        labels = Y[idx]
        if dissimilarity == "euclidean":
            X = X[idx]
        else:
            X = X[np.ix_(idx, idx)]
    else:
        labels = Y

    if dissimilarity == "euclidean":
        dissimilarities = euclidean_distances(X)
    else:
        dissimilarities = X

    rdfs = _discr_rdf(dissimilarities, labels)
    stat = np.nanmean(rdfs)

    if return_rdfs:
        return stat, rdfs
    else:
        return stat


class NdmgDirectory:
    """
    Contains methods for use on a `ndmg` output directory.
    Top-level object of this package.
    Parameters
    ----------
    directory : str
    filepath or s3 url to the directory containing graph outputs.
    if s3, input should be `s3://bucket-prefix/`.
    if filepath, input should be the absolute path.
    directory : Path
    Path object to the directory passed to NdmgGraphs.
    Takes either an s3 bucket or a local directory string as input.
    atlas : str
    atlas to get graph files of.
    delimiter : str
    delimiter in graph files.
    Attributes
    ----------
    files : list, sorted
    List of path objects corresponding to each edgelist.
    name : str
    name of dataset.
    to_directory : func
    Send all graph files to a directory of your choosing
    """

    def __init__(self, directory, atlas="", suffix="csv", delimiter=" "):
        if not isinstance(directory, (str, Path)):
            message = f"Directory must be type str or Path. Instead, it is type {type(directory)}."
            raise TypeError(message)
        self.s3 = str(directory).startswith("s3:")
        self.directory = directory
        self.delimiter = delimiter
        self.atlas = atlas
        self.suffix = suffix
        self.files = self._files(directory)
        self.name = self._get_name()
        if not len(self.files):
            raise ValueError(f"No graphs found in {str(self.directory)}.")

    def __repr__(self):
        return f"NdmgDirectory : {str(self.directory)}"

    def _files(self, directory):
        """
        From a directory or s3 bucket containing edgelist files,
        return a list of edgelist files,
        sorted.
        This property is ground truth for how the scans should be sorted.
        Parameters
        ----------
        path : directory of edgelist files or s3 bucket
        Returns
        -------
        output : list, sorted
        Sorted list of Paths to files in `path`.
        """
        output = []
        # grab files from s3 instead of locally
        if self.s3:
            output = self._get_s3(directory, atlas=self.atlas, suffix=self.suffix)
        else:
            self.directory = Path(self.directory)
            for dirname, _, files in os.walk(directory):
                file_ends = list(
                    filter_graph_files(files, suffix=self.suffix, atlas=self.atlas)
                )
                graphnames = [
                    Path(dirname) / Path(graphname) for graphname in file_ends
                ]
                if all(graphname.exists for graphname in graphnames):
                    output.extend(graphnames)
        return sorted(output)

    def _get_s3(self, path, **kwargs):
        output = []
        # parse bucket and path from self.directory
        # TODO: this breaks if the s3 directory structure changes
        bucket, prefix = parse_path(path)
        local_dir = Path.home() / Path(f".ndmg_s3_dir/{prefix}")
        if self.atlas:
            local_dir = local_dir / Path(self.atlas)
        else:
            local_dir = local_dir / Path("no_atlas")
        self.directory = local_dir

        # if our local_dir already has graph files in it, just use that
        is_dir = local_dir.is_dir()
        has_graphs = False
        if is_dir:
            has_graphs = filter_graph_files(
                local_dir.iterdir(), return_bool=True, **kwargs
            )

        # If has_graphs just got toggled, return all the graphs.
        if has_graphs:
            print(f"Local path {local_dir} found. Using that.")
            graphs = filter_graph_files(local_dir.iterdir(), **kwargs)
            return list(graphs)

        print(f"Downloading objects from s3 into {local_dir}...")

        # get generator of object names
        unfiltered_objs = get_matching_s3_objects(
            bucket, prefix=prefix, suffix=self.suffix
        )
        objs = filter_graph_files(unfiltered_objs, **kwargs)

        # download each s3 graph and append local filepath to output
        for obj in objs:
            name = Path(obj).name
            local = str(local_dir / Path(name))
            print(f"Downloading {name} ...")
            s3_download_graph(bucket, obj, local)
            output.append(local)

        # return
        if not output:
            raise ValueError("No graphs found in the directory given.")
        return output

    def _get_name(self):
        """
        return directory beneath ".ndmg_s3_dir".
        Returns
        -------
        str
        name of dataset.
        """
        if not self.s3:
            return self.directory.name

        parts = Path(self.directory).parts
        dataset_index = parts.index(".ndmg_s3_dir") + 1
        return parts[dataset_index]

    def to_directory(self, dst=None):
        """
        Send all `self.files`to `directory`.
        Parameters
        ----------
        directory : str or Path
        directory to send files to.
        """
        if dst is None:
            dst = self.directory / "graph_outputs"
        p = Path(dst).resolve()
        p.mkdir(parents=True, exist_ok=True)
        for filename in self.files:
            shutil.copy(filename, p)


class NdmgGraphs(NdmgDirectory):
    """
    NdmgDirectory which contains graph objects.
    Parameters
    ----------
    delimiter : str
    The delimiter used in edgelists
    Attributes
    ----------
    delimiter : str
    The delimiter used in edgelists
    vertices : np.ndarray
    sorted union of all nodes across edgelists.
    graphs : np.ndarray, shape (n, v, v), 3D
    Volumetric numpy array, n vxv adjacency matrices corresponding to each edgelist.
    graphs[0, :, :] corresponds to files[0].
    subjects : np.ndarray, shape n, 1D
    subject IDs, sorted array of all subject IDs in `dir`.
    subjects[0] corresponds to files[0].
    sessions : np.ndarray, shape n, 1D
    session IDs, sorted array of all sessions.
    sessions[0] corresponds to files[0].
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nx_graphs = self._nx_graphs()
        self.vertices = self._vertices()
        self.sort_nx_graphs()  # get vertices, sort nx graphs
        self.graphs = self._graphs()
        self.subjects = self._parse()[0]
        self.sessions = self._parse()[1]

    def __repr__(self):
        return f"NdmgGraphs : {str(self.directory)}"

    def _nx_graphs(self):
        """
        List of networkx graph objects. Hidden property, mainly for use to calculate vertices.
        Returns
        -------
        nx_graphs : List[nx.Graph]
        List of networkX graphs corresponding to subjects.
        """
        files_ = [str(name) for name in self.files]
        nx_graphs = [
            nx.read_weighted_edgelist(f, nodetype=int, delimiter=self.delimiter)
            for f in files_
        ]
        return nx_graphs

    def _vertices(self):
        """
        Calculate the unioned number of nodes across all graph files.
        Returns
        -------
        np.array
        Sorted array of unioned nodes.
        """
        return np.sort(reduce(np.union1d, [G.nodes for G in self.nx_graphs]))

    def _graphs(self):
        """
        volumetric numpy array, shape (n, v, v),
        accounting for isolate nodes by unioning the vertices of all component edgelists,
        sorted in the same order as `self.files`.
        Returns
        -------
        graphs : np.ndarray, shape (n, v, v), 3D
        Volumetric numpy array, n vxv adjacency matrices corresponding to each
        edgelist.
        graphs[0, :, :] corresponds to files[0].D
        """
        list_of_arrays = import_edgelist(self.files, delimiter=self.delimiter)
        if not isinstance(list_of_arrays, list):
            list_of_arrays = [list_of_arrays]
        return np.atleast_3d(list_of_arrays)

    def _parse(self):
        """
        Get subject IDs
        Returns
        -------
        out : np.ndarray
        Array of strings. Each element is a subject ID.
        """
        # pattern = r"(?<=sub-|ses-)(¥w*)(?=_ses|_measure-correlation)" #_measure-correlation used to be _dwi
        pattern = r"(?<=sub-)(\d*)(_ses-)(\d*)"
        # subjects = [re.findall(pattern, str(edgelist))[0] for edgelist in self.files]
        # sessions = [re.findall(pattern, str(edgelist))[1] for edgelist in self.files]
        subjects = [re.findall(pattern, str(edgelist))[0][0] for edgelist in self.files]
        sessions = [re.findall(pattern, str(edgelist))[0][2] for edgelist in self.files]
        return np.array(subjects), np.array(sessions)

    def sort_nx_graphs(self):
        """
        Ensure that all networkx graphs have the same number of nodes.
        Returns
        -------
        None
        """
        for graph in self.nx_graphs:
            graph.add_nodes_from(self.vertices)


class NdmgStats(NdmgGraphs):
    """Compute statistics from a ndmg directory.
    Parameters
    ----------
    X : np.ndarray, shape (n, v*v), 2D
    numpy array, created by vectorizing each adjacency matrix and stacking.
    Methods
    -------
    pass_to_ranks : returns None
    change state of object.
    calls pass to ranks on `self.graphs`, `self.X`, or both.
    save_X_and_Y : returns None
    Saves `self.X` and `self.Y` into a directory.
    discriminability : return float
    discriminability statistic for this dataset
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.X = self._X()
        self.Y = self.subjects

    def __repr__(self):
        return f"NdmgStats : {str(self.directory)}"

    def __len__(self):
        return len(self.files)

    def _X(self, graphs=None):
        """
        this will be a single matrix,
        created by vectorizing each array in `self.graphs`,
        and then appending that array as a row to X.
        Parameters
        ----------
        graphs : None or np.ndarray
        if None, graphs will be `self.graphs`.
        Returns
        -------
        X : np.ndarray, shape (n, v*v), 2D
        numpy array, created by vectorizing each adjacency matrix and stacking.
        """
        if graphs is None:
            graphs = self.graphs
        if graphs.ndim == 3:
            n, v1, v2 = np.shape(graphs)
            return np.reshape(graphs, (n, v1 * v2))
        elif len(self.files) == 1:
            warnings.warn("Only one graph in directory.")
            return graphs
        else:
            raise ValueError("Dimensionality of input must be 3.")

    def save_X_and_Y(self, output_directory="cwd", output_name=""):
        """
        Save `self.X` and `self.subjects` into an output directory.
        Parameters
        ----------
        output_directory : str, default current working directory
        Directory in which to save the output.
        Returns
        -------
        namedtuple with str
        namedtuple of `name.X, name.Y`. Paths to X and Y.
        """
        if not output_name:
            output_name = self.name

        if output_directory == "cwd":
            output_directory = Path.cwd()

        p = Path(output_directory)
        p.mkdir(parents=True, exist_ok=True)

        X_name = f"{str(p)}/{output_name}_X.csv"
        Y_name = f"{str(p)}/{output_name}_Y.csv"

        np.savetxt(X_name, self.X, fmt="%f", delimiter=",")
        np.savetxt(Y_name, self.subjects, fmt="%s")

        name = namedtuple("name", ["X", "Y"])
        return name(X_name, Y_name)

    @replace_doc(discr_stat.__doc__)
    def discriminability(self, PTR=True, **kwargs):
        """
        Attach discriminability functionality to the object.
        See `discr_stat` for full documentation.
        Returns
        -------
        stat : float
        Discriminability statistic.
        """
        if PTR:
            graphs = np.copy(self.graphs)
            # No need to pass to ranks and normalize if it's a correlation??
            if PTR == True:
                graphs = np.array([pass_to_ranks(graph + 2) for graph in graphs])
            X = self._X(graphs)
            return discr_stat(X, self.Y, **kwargs)

        return discr_stat(self.X, self.Y, **kwargs)

    def visualize(self, i, savedir=""):
        """
        Visualize the ith graph of self.graphs, passed-to-ranks.
        Parameters
        ----------
        i : int
        Graph to visualize.
        savedir : str, optional
        Directory to save graph into.
        If left empty, do not save.
        """
        nmax = np.max(self.graphs)

        if isinstance(i, int):
            graph = pass_to_ranks(self.graphs[i])
            sub = self.subjects[i]
            sesh = self.sessions[i]

        elif isinstance(i, np.ndarray):
            graph = pass_to_ranks(i)
            sub = ""
            sesh = ""
        else:
            raise TypeError("Passed value must be integer or np.ndarray.")

        viz = heatmap(
            graph, title=f"sub-{sub}_session-{sesh}", xticklabels=True, yticklabels=True
        )

        # set color of title
        viz.set_title(viz.get_title(), color="black")

        # set color of colorbar ticks
        viz.collections[0].colorbar.ax.yaxis.set_tick_params(color="black")

        # set font size and color of heatmap ticks
        for item in viz.get_xticklabels() + viz.get_yticklabels():
            item.set_color("black")
            item.set_fontsize(7)

        if savedir:
            p = Path(savedir).resolve()
            if not p.is_dir():
                p.mkdir()
            plt.savefig(
                p / f"sub-{sub}_sesh-{sesh}.png",
                facecolor="white",
                bbox_inches="tight",
                dpi=300,
            )
        return viz

    def visualize(self, i, savedir=""):
        """
        Visualize the ith graph of self.graphs, passed-to-ranks.
        Parameters
        ----------
        i : int
        Graph to visualize.
        savedir : str, optional
        Directory to save graph into.
        If left empty, do not save.
        """

        nmax = np.max(self.graphs)

        if isinstance(i, int):
            graph = pass_to_ranks(self.graphs[i])
            sub = self.subjects[i]
            sesh = ""  # TODO
        elif isinstance(i, np.ndarray):
            graph = pass_to_ranks(i)
            sub = ""
            sesh = ""
        else:
            raise TypeError("Passed value must be integer or np.ndarray.")

        viz = heatmap(
            graph,
            title=f"sub-{sub}_session-{sesh}",
            xticklabels=True,
            yticklabels=True,
            vmin=0,
            vmax=1,
        )

        # set color of title
        viz.set_title(viz.get_title(), color="black")

        # set color of colorbar ticks
        viz.collections[0].colorbar.ax.yaxis.set_tick_params(color="black")

        # set font size and color of heatmap ticks
        for item in viz.get_xticklabels() + viz.get_yticklabels():
            item.set_color("black")
            item.set_fontsize(7)

        if savedir:
            p = Path(savedir).resolve()
            if not p.is_dir():
                p.mkdir()
            plt.savefig(
                p / f"sub-{sub}_sesh-{sesh}.png",
                facecolor="white",
                bbox_inches="tight",
                dpi=300,
            )
        else:
            plt.show()

        plt.cla()


def url_to_ndmg_dir(urls):
    """
    take a list of urls or filepaths,
    get a dict of NdmgGraphs objects
    Parameters
    ----------
    urls : list
    list of urls or filepaths.
    Each element should be of the same form as the input to a `NdmgGraphs` object.
    Returns
    -------
    dict
    dict of {dataset:NdmgGraphs} objects.
    Raises
    ------
    TypeError
    Raises error if input is not a list.
    """
    # checks for type
    if isinstance(urls, str):
        urls = [urls]
    if not isinstance(urls, list):
        raise TypeError("urls must be a list of URLs.")

    # appends each object
    return_value = {}
    for url in urls:
        try:
            val = NdmgStats(url)
            key = val.name
            return_value[key] = val
        except ValueError:
            warnings.warn(f"Graphs for {url} not found. Skipping ...")
            continue
    return return_value


def _discr_rdf(dissimilarities, labels):
    """
    A function for computing the reliability density function of a dataset.
    Parameters
    ----------
    dissimilarities : array, shape (n_samples, n_features) or (n_samples, n_samples)
    Input data. If dissimilarity=='precomputed', the input should be the
    dissimilarity matrix.
    labels : 1d-array, shape (n_samples)
    Input labels.
    Returns
    -------
    out : array, shape (n_samples, max{len(id)})
    Rdfs for each sample. Only returned if ``return_rdfs==True``.
    """
    check_X_y(dissimilarities, labels, accept_sparse=True)

    rdfs = []
    for i, label in enumerate(labels):
        di = dissimilarities[i]

        # All other samples except its own label
        idx = labels == label
        Dij = di[~idx]

        # All samples except itself
        idx[i] = False
        Dii = di[idx]

        rdf = [1 - ((Dij < d).sum() + 0.5 * (Dij == d).sum()) / Dij.size for d in Dii]
        rdfs.append(rdf)

    out = np.full((len(rdfs), max(map(len, rdfs))), np.nan)
    for i, rdf in enumerate(rdfs):
        out[i, : len(rdf)] = rdf

    return out


def discrim_runner(input_dir, atlas, ptr):
    m = NdmgStats(f"{input_dir}/{atlas}")
    discrim = m.discriminability(PTR=ptr)
    print(f"{atlas} analyzed: {discrim}")
    return discrim


def avgconnectome(input_dir, output_dir, atlas):
    means = OrderedDict()
    var = OrderedDict()

    # get list of all files belonging to atlas:
    connectomes = os.listdir(f"{input_dir}/{atlas}")

    # itterate through list and calculate mean and variance of edgelist
    c = 0
    files_ = [f"{input_dir}/{atlas}/{str(name)}" for name in connectomes]
    # print('stop, please')
    # nx_graphs = [
    #    nx.read_weighted_edgelist(f, nodetype=int, delimiter=" ")
    #    for f in files_
    # ]

    list_of_arrays, verts = import_edgelist(files_, delimiter=" ", return_vertices=True)
    if not isinstance(list_of_arrays, list):
        list_of_arrays = [list_of_arrays]

    ptr_list_of_arrays = np.array([pass_to_ranks(array) for array in list_of_arrays])

    stack = np.atleast_3d(list_of_arrays)
    ptr_stack = np.atleast_3d(ptr_list_of_arrays)

    N, _, _ = stack.shape

    # Calculate mean and variance:
    mean = np.mean(stack, axis=0)
    var = np.var(stack, axis=0)
    ptr_mean = np.mean(ptr_stack, axis=0)
    ptr_var = np.var(ptr_stack, axis=0)

    # Check that number of vertices and dimensions of averaged connectomes match up
    if len(verts) != mean.shape[0]:
        print(
            f"WARNING: Number of nodes and dimension of connectome do not match for: {atlas}!"
        )

    np.savetxt(f"{output_dir}/{atlas}/verts.csv", verts, fmt="%d", delimiter=" ")

    # Convert matrix to edgelists
    a = sum(range(1, len(verts)))
    arr = np.zeros((a, 3))
    z = 0
    for num in range(len(mean)):
        for i in range(len(mean[num])):
            if i > num:
                # print(f'{num+1} {i+1} {my_data[num][i]}')
                arr[z][0] = f"{int(verts[num])}"  # f'{num+1}'
                arr[z][1] = f"{int(verts[i])}"
                arr[z][2] = mean[num][i]
                z = z + 1

    np.savetxt(f"{output_dir}/{atlas}/mean.csv", arr, fmt="%d %d %f", delimiter=" ")

    arr = np.zeros((a, 3))
    z = 0
    for num in range(len(var)):
        for i in range(len(var[num])):
            if i > num:
                # print(f'{num+1} {i+1} {my_data[num][i]}')
                arr[z][0] = f"{int(verts[num])}"  # f'{num+1}'
                arr[z][1] = f"{int(verts[i])}"
                arr[z][2] = var[num][i]
                z = z + 1

    np.savetxt(f"{output_dir}/{atlas}/variance.csv", arr, fmt="%d %d %f", delimiter=" ")

    arr = np.zeros((a, 3))
    z = 0
    for num in range(len(ptr_mean)):
        for i in range(len(ptr_mean[num])):
            if i > num:
                # print(f'{num+1} {i+1} {my_data[num][i]}')
                arr[z][0] = f"{int(verts[num])}"  # f'{num+1}'
                arr[z][1] = f"{int(verts[i])}"
                arr[z][2] = ptr_mean[num][i]
                z = z + 1

    np.savetxt(f"{output_dir}/{atlas}/mean-ptr.csv", arr, fmt="%d %d %f", delimiter=" ")

    arr = np.zeros((a, 3))
    z = 0
    for num in range(len(ptr_var)):
        for i in range(len(ptr_var[num])):
            if i > num:
                # print(f'{num+1} {i+1} {my_data[num][i]}')
                arr[z][0] = f"{int(verts[num])}"  # f'{num+1}'
                arr[z][1] = f"{int(verts[i])}"
                arr[z][2] = ptr_var[num][i]
                z = z + 1

    np.savetxt(
        f"{output_dir}/{atlas}/variance-ptr.csv", arr, fmt="%d %d %f", delimiter=" "
    )

    print(f"Averaged connectomes and variances saved for: {atlas}!")

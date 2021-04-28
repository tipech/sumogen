import os, base64, sys
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse
import subprocess

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
        print("set up sumolib env")
else:   
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib

class OSMNet():
    """Connects to OpenStreetMap, downloads and converts specified network."""

    def __init__(self, api="www.overpass-api.de/api/interpreter"):
        """Initialize OSM downloader
        
        Params
        ------
        api : str (default: "www.overpass-api.de/api/interpreter")
            API URL to use for download
        """

        # parse url
        if "http" in api:
            url = urlparse(api)
        else:
            url = urlparse("https://" + api)

        self.path = url.path

        # proxy check
        if os.environ.get("https_proxy") is not None:
            headers = {}
            proxy_url = urlparse(os.environ.get("https_proxy"))
            if proxy_url.username and proxy_url.password:
                auth = '%s:%s' % (proxy_url.username, proxy_url.password)
                headers['Proxy-Authorization'] = 'Basic ' + base64.b64encode(auth)
            self.conn = HTTPSConnection(proxy_url.hostname, proxy_url.port)
            self.conn.set_tunnel(url.hostname, 443, headers)
        else:

            # HTTP vs HTTPS check
            if url.scheme == "https":
                self.conn = HTTPSConnection(url.hostname, url.port)
            else:
                self.conn = HTTPConnection(url.hostname, url.port)


    def download(self, north, south, west, east, osm_file):
        """Get the OSM network for specified coords and store to file.

        Params
        ------
        north, south, west, east : float
            Geo coordinates of input area bounding box
        osm_file : str
            Output OSM network file name/path
        """

        self.conn.request("POST", "/" + self.path, """
        <osm-script timeout="240" element-limit="1073741824">
        <union>
           <bbox-query n="%s" s="%s" w="%s" e="%s"/>
           <recurse type="node-relation" into="rels"/>
           <recurse type="node-way"/>
           <recurse type="way-relation"/>
        </union>
        <union>
           <item/>
           <recurse type="way-node"/>
        </union>
        <print mode="body"/>
        </osm-script>""" % (north, south, west, east))
        print("Downloading map data")
        response = self.conn.getresponse()
        print(response.status, response.reason)
        if response.status == 200:
            out = open(os.path.join(os.getcwd(), osm_file), "wb")
            out.write(response.read())
            out.close()


    def convert(self, osm_file, net_file):
        """Convert OSM network to SUMO format using netconvert.

        Params
        ------
        osm_file : str
            OSM network file name/path
        net_file : str
            Output SUMO network file name/path
        """

        # get binary
        netconvert = sumolib.checkBinary('netconvert')

        # additional options
        netconvertOpts = [netconvert]
        netconvertOpts += ['--sidewalks.guess', '--crossings.guess']

        # input and output files
        netconvertOpts += ['--osm-files', osm_file]
        netconvertOpts += ['--output-file', net_file]

        return subprocess.call(netconvertOpts)


    def get(self, north, south, west, east, net_file):
        """Get OSM network and convert to SUMO format.
        
        Params
        ------
        north, south, west, east : float
            Coordinates of input bounding box
        net_file : str
            Output SUMO network file name/path
        """

        tmp_file = "tmp.osm.xml"
        self.download(north, south, west, east, tmp_file)
        success = self.convert(tmp_file, net_file)
        os.remove(tmp_file)

        return success
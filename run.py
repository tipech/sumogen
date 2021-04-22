import subprocess, os, sys
from sumogen.osmnet import OSMNet
from sumogen.demandgen import DemandGenerator

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
        print("set up sumolib env")
else:   
    sys.exit("please declare environment variable 'SUMO_HOME'")



directory = 'sample'
n = 100
days = 10


# download SUMO road network
downloader = OSMNet()
downloader.get(43.7845, 43.7571, -79.5437, -79.4763, "york.net.xml")

# generate demand
generator = DemandGenerator("york.net.xml", nr_pois=100, seed=2)
config_file, output_file = generator.make_sumo_config(
        n=n, days=days, store_dir=directory, plot=True)

# in case sumo failed, reload
# config_file = '{}_{}_config.sumocfg'.format(n, days)
# output_file = '{}_{}_output.xml'.format(n, days)

# run sumo
subprocess.run(["sumo", config_file], cwd=directory)

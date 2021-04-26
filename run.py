from sumogen.osmnet import OSMNet
from sumogen.demandgen import DemandGenerator


# download SUMO road network
download_success = OSMNet().get(43.7845, 43.7571, -79.5437, -79.4763, "york.net.xml")

# generate demand get pedestrian trajectory data
generator = DemandGenerator("york.net.xml", nr_pois=100, seed=2)
output_file = generator.get_trajectories(n=10, days=10, store_dir='sample', geo_format=False, plot=False)
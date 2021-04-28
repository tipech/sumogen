import os, sys, subprocess
import random, math
import numpy as np
import networkx as nx
import xml.etree.cElementTree as ET
from shutil import copyfile
from itertools import combinations


if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'.")

import sumolib
duarouter = sumolib.checkBinary('duarouter')

from .entities import Pedestrian, Trip
from .plotting import ActivityPlot
from ..sumo import SUMO


def normpdf(x, mean, sd):
    """Get a probability density function value."""
    var = float(sd)**2
    denom = (2*math.pi*var)**.5
    num = math.exp(-(float(x)-float(mean))**2/(2*var))
    return num/denom



class DemandGenerator():
    """Responsible for creating valid pedestrian routes for SUMO."""

    def __init__(self, network,
        timestep_length=60, day_night_cycle=True, week_cycle=True,
        day_hours=12, average_stay_duration=60*60,
        activity_levels=10, al_mu=5.5, al_sigma=2.5,
        nr_pois=1000, nr_core_pois=10,
        favorites=True, common_favorites=True,
        walk_speed=0.8, seed=None):
        """Setup the trip generator with specified parameters.

        Parameters
        ----------
        network : str
            The network file.
        timestep_length : int (optional, default: 60 | 1 minute)
            How many seconds is a time unit.
        day_night_cycle : boolean (optional, default: True)
            Whether to schedule trips mostly during the day.
        week_cycle : boolean (optional, default: True)
            Whether to reduce traffic for weekends.
        day_hours : int (optional, default: 12)
            How many hours long is a day vs night.
        average_stay_duration : int (optional, default: 3600 | 1 hour)
            How many seconds a person stays somewhere on average.
        activity_levels : int (optional, default: 10)
            Number of total activity levels.
        al_mu : float (optional, default: 5.5)
            Mean for the active level distribution.
        al_sigma : float (optional, default: 2.5)
            Sigma for the active level distribution.
        nr_pois : int (optional, default: 1000)
            Number of selected points of interest, 0 means all edges in net.
        nr_core_pois : int (optional, default: 10)
            Number of initial core pois reachable by every other.
        favorites : boolean (optional, default: True)
            Whether each pedestrian will prefer some places over others.
        common_favorites : boolean (optional, default: True)
            Whether all pedestrians will prefer some places over others.
        walk_speed : float (optional, default: 0.8)
            Pedestrian walking speed in m/s.
            Setting it below the 1m/s SUMO value approximates delays.
        seed : int (optional, default: None - random seed)
            Seed for the random number generator.
        """

        self.network = network

        self.timestep_length = timestep_length 
        self.week_cycle = week_cycle
        self.day_hours = day_hours
        self.average_stay_duration = average_stay_duration
        self.activity_levels = activity_levels
        self.al_mu = al_mu
        self.al_sigma = al_sigma
        self.favorites = favorites
        self.common_favorites = common_favorites

        self.nr_pois = nr_pois
        self.nr_core_pois = nr_core_pois
        self.walk_speed = walk_speed
        self.seed = seed

        # set custom seed if provided
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        print("Setting up route generator.")
        # get time distribution of trips in minutes
        if day_night_cycle:
            day_distr = [normpdf(x, (9/24) * 24*60, 24*9)
                        + normpdf(x, (13/24) * 24*60, 24*12)
                        + normpdf(x, (18/24) * 24*60, 24*9)
                            for x in range(24*60)]
            self.time_distr = [d/sum(day_distr) for d in day_distr]
        else:
            self.time_distr = [round(1/(24*60))  for x in range(24*60)]

        # if not given a pedestrian-fixed network, fix it
        if ".fixed" not in network:
            network = self.fix_sidewalks(network)
        self.net = sumolib.net.readNet(network)

        # get all fully accesible points in the graph
        self.pois = self.get_pois(network)

        if common_favorites:
            self.common_poi_distr = [
                normpdf(x, len(self.pois)/2, len(self.pois)/4)
                for x in range(len(self.pois))]


        print("Route generator set up.")


    def fix_sidewalks(self, network):
        """Fix network edge pedestrian configuration

        SUMO doesn't correctly generate connections that allow
        pedestrians when sidewalks are generated.
        To fix this, we allow pedestrians to walk on any lane of
        an edge as long as it has a sidewalk.
        """

        tree = ET.parse(network)
        for edge in tree.findall('edge'):
            
            # if any lane of edge allows pedestrians
            if any('pedestrian' in str(lane.get('allow'))
                        for lane in edge.findall('lane')):

                # allow pedestrians in all lanes
                for lane in edge.findall('lane'):
                    disallowed = lane.get('disallow')
                    if disallowed is not None:
                        disallowed = disallowed.replace('pedestrian ', '')
                        lane.set('disallow', disallowed)

        # save resulting tree to file
        filename = network.replace('.xml', '.fixed.xml')
        tree.write(filename)
        return filename


    def get_connected_edges(self, network):
        """Get the edges of the biggest component in the graph."""

        # build a graph from road network edges
        G = nx.Graph()
        for edge in self.net.getEdges():
            if edge.allows("pedestrian"):
                G.add_edge(edge.getFromNode().getID(),
                                    edge.getToNode().getID(), edge=edge)

        # get only edges in biggest connected component
        comp_sizes = [(len(c), c) for c in nx.connected_components(G)]
        core_comp = sorted(comp_sizes, reverse=True, key=lambda x:x[0])[0][1]
        isolated = set(G.nodes()) - set(core_comp)
        G.remove_nodes_from(isolated)
        return [edge[2] for edge in G.edges(data='edge')]


    def get_core_pois(self, edges):
        """Select a small sample of POIs that all connect with each other."""

        # randomly select some POIS and put them in a graph
        pool = np.random.choice(edges, size=self.nr_core_pois, replace=False)
        poi_G = nx.Graph()
        possible_edges = list(combinations(pool, 2))

        # examine all possible edges and add them to graph if a path exists
        for i, (edge_from, edge_to) in enumerate(possible_edges):
            print("Generating core points of interest: {}%"
                .format(int(100 * i/len(possible_edges))), end="\r")

            if (self.has_path(edge_from, edge_to)
                and self.has_path(edge_to, edge_from)):
                poi_G.add_edge(edge_from.getID(), edge_to.getID())

        # get the largest fully connected component (maximal clique)
        core_pois = [self.net.getEdge(poi)
                        for poi in list(nx.find_cliques(poi_G))[0]]

        print("Generated {} core points of interest.      "
            .format(len(core_pois)))
        return core_pois


    def get_pois(self, network):
        """Get all fully accesible POIs in the network."""

        edges = self.get_connected_edges(network)
        core_pois = self.get_core_pois(edges)
        nr_edges = len(edges)
        pois = []

        # get points of interest as long as they connect to core pois
        while len(edges) > 0 and (
            self.nr_pois == 0 or len(pois) < self.nr_pois):

            # track progress according to all possible edges
            if self.nr_pois == 0:
                print("Generating points of interest: {:.2f}%"
                    .format(100 - 100 * len(edges)/nr_edges), end="\r")
            
            # track progress with number of pois
            else:
                print("Generating points of interest: {:.2f}%"
                    .format(100 * len(pois)/self.nr_pois), end="\r")

            poi_candidate = random.choice(edges)
            edges.remove(poi_candidate)

            # make sure candidate connects to all core pois
            if (self.has_path(poi_candidate, core_pois[0])
                and self.has_path(core_pois[0], poi_candidate)):
                pois.append(poi_candidate)

        print("Generated {} points of interest.      ".format(len(pois)))
        return pois

    
    def get_poi_distribution(self):
        """Get visit likelihood of POIs for a single pedestrian."""

        poi_distr = [0] * len(self.pois)

        # add a common favorite distribution
        if self.common_favorites:
            for i in range(len(poi_distr)):
                poi_distr[i] += self.common_poi_distr[i]
        
        # add a  personal favorite distribution
        if self.favorites:
            personal_distr = [normpdf(x, len(self.pois)/2, len(self.pois)/16)
                                for x in range(len(self.pois))]
            shuffled_distr = random.sample(personal_distr, len(self.pois))

            for i in range(len(poi_distr)):
                poi_distr[i] += shuffled_distr[i]
        
        # normalize and make sure they add to 1
        poi_distr =  [p/sum(poi_distr) for p in poi_distr]
        if sum(poi_distr) < 1:
            index = random.randrange(len(poi_distr))
            poi_distr[index] += (1 - sum(poi_distr))
        return poi_distr


    def check_duarouter_path(self, edge_from, edge_to):
        """Check if duarouter likes this path."""

        test_trip = Trip("tmp", "tmp", 0, [(edge_from.getID(),
                                        edge_to.getID())], [1], [1], [1])
        self.store_trips([test_trip], "tmp.xml")
        null_output = open(os.devnull, 'w')
        route = subprocess.run([duarouter, "-W","-n " + self.network,
                                "-r tmp.xml", "-o /dev/null"],
                                stdout=null_output, stderr=null_output)
        os.remove("tmp.xml")
        return route.returncode == 0


    def get_path(self, edge_from, edge_to):
        """Get a single path between two points on the network."""

        return self.net.getShortestPath(edge_from,edge_to,vClass="pedestrian")


    def has_path(self, edge_from, edge_to, with_duarouter = False):
        """Determine if a single path between two points exists."""

        path = self.get_path(edge_from, edge_to)[0] is not None
        if not with_duarouter or not path:
            return path

        return check_duarouter_path(edge_from, edge_to)


    def generate_pedestrians(self, nr_pedestrians):
        """Generate a specifed number of pedestrians.

        Parameters
        ----------
        nr_pedestrians : int
            Number of pedestrians generated.
        """

        pedestrians = []
        for i in range(nr_pedestrians):

            # get pedestrian home, activity level and daily travel time
            # every day will travel for 16 hours * (level^2 * 1%)
            home = random.choice(self.pois)
            level = int(min(self.activity_levels, max(0,
                np.random.normal(self.al_mu, self.al_sigma))))
            daily_time = ((self.day_hours/24) * 24*60*60
                            * (pow(level, 2) * 0.01))
            # daily_time = (self.day_hours/24) * 24*60*60 * (level * 0.1)

            # get distribution of pois visit frequency for this person
            poi_distr = self.get_poi_distribution()

            # generate pedestrian
            ped = Pedestrian(i, home, self.pois, poi_distr, level, daily_time)
            pedestrians.append(ped)
            
            print("Generating pedestrians: {:.2f}%"
                .format(100 * i/nr_pedestrians), end="\r")
        print("Generating pedestrians: 100.00%")
        return pedestrians


    def get_duration(self, source, target):
        """Get the duration of a single path"""

        path = self.get_path(source, target)
        return int(path[1] / self.walk_speed)


    def generate_path_sequence(self, pedestrian):
        """Get a single path sequence for a pedestrian."""

        # activity levels 8,9,10 can do     home->1->2->3->home
        # activity levels 5,6,7 can do      home->1->2->home
        # activity levels 0,1,2,3,4 can do  home->1->home
        max_trips = round(pedestrian.level/3)
        paths = []
        durations = []

        # start from home
        target = pedestrian.home

        # if there's still time, travel to more stops and wait there
        while len(paths) == 0 or (len(paths) < max_trips 
            and pedestrian.remaining_time > 0):
            source = target
            target = pedestrian.get_poi()
            duration = self.get_duration(source, target)
            paths.append((source.getID(), target.getID()))
            durations.append(duration)
            pedestrian.remaining_time -= duration

        # last trip home
        source = target
        target = pedestrian.home
        duration = self.get_duration(source, target)
        paths.append((source.getID(), target.getID()))
        durations.append(duration)
        pedestrian.remaining_time -= duration

        return paths, durations


    def generate_trip(self, pedestrian, day):
        """Get a single trip for a pedestrian."""

        paths, durations = self.generate_path_sequence(pedestrian)
        wait_times = np.random.choice(range(self.average_stay_duration * 2),
            size=len(paths)-1)
        pedestrian.remaining_time -= sum(wait_times)
        times = []

        # get time in the day this trip started
        time_start = np.random.choice(range(int(24*60)), p=self.time_distr)*60
        times.append(time_start)

        # get remaining trip times
        for t in range(1, len(paths)):
            times.append(times[t-1] + durations[t-1] + wait_times[t-1])

        # incremental trip id
        trip_id = "{}_{}".format(pedestrian.id, pedestrian.trip_count)
        pedestrian.trip_count += 1

        return Trip(trip_id, pedestrian.id, day * 24*60*60, paths,
            times, durations, wait_times)


    def generate_trips(self, pedestrians, days):
        """Generate trips for given pedestrians over many days.

        Parameters
        ----------
        pedestrians : list of Pedestrian
            Pedestrians to generate trips for.
        days : int
            Number of days to generate trips for.
        """

        trips = []

        # day 0 doesn't count
        for ped in pedestrians:
            print("Generating trips for day: 0/{}".format(days), end="\r")
            ped.remaining_time += ped.daily_travel_time/2
            while ped.remaining_time > 0:
                self.generate_trip(ped, -1)

        # get trips
        for day in range(days):
            print("Generating trips for day: {}/{}".format(day+1, days),
                end="\r")
            for ped in pedestrians:

                # add time for today, adjust for weekends
                if self.week_cycle and day % 7 == 0 or day % 7 == 1:
                    ped.remaining_time += ped.daily_travel_time / 2
                else:
                    ped.remaining_time += ped.daily_travel_time
                    
                while ped.remaining_time > 0:
                    trips.append(self.generate_trip(ped, day))
        print("Generated {} trips for {} timestamps."
            .format(len(trips), days * 24*60*60))

        trips = sorted(trips, key=lambda t:t.start_time)
        return trips


    def store_trips(self, trips, filename):
        """Write generated trips to xml file."""

        # write output string
        xml_string = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<routes"
            + " xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
            + "xsi:noNamespaceSchemaLocation=\""
            + "http://sumo.dlr.de/xsd/routes_file.xsd\">\n"
            + "<vType id=\"ped_pedestrian\" vClass=\"pedestrian\"/>\n")
        for trip in trips:
            xml_string += trip.to_xml()
        xml_string += "</routes>"

        # write output file
        with open(filename, "w") as file:
            file.write(xml_string)


    def store_routes(self, trips_path, routes_path):
        """Write generated routes to xml file."""

        print("Generating routes file.")
        router = subprocess.run([duarouter, "-W","-n " + self.network,
                    "--repair", "-r " + trips_path, "-o " + routes_path])

        # duarouter sometimes messes up the trip depart times, read and fix it
        with open(trips_path, "r") as file:
            trips_root = ET.parse(file).getroot()
            trip_departs = {person.get('id'): int(person.get('depart'))
                            for person in trips_root.findall('person')}

        with open(routes_path, "r") as file:
            routes_tree = ET.parse(file)
        routes_root = routes_tree.getroot()

        # get correct departure times from trips file, sorted
        person_elems = []
        for person in routes_root.findall('person'):
            depart =  trip_departs[person.get('id')]
            elem = person
            elem.set('depart', "{:.2f}".format(depart))
            person_elems.append((depart, elem))
        person_elems = sorted(person_elems, key=lambda x:x[0])

        # create a new xml root with correct times and store file
        new_root = ET.Element("routes")
        for k,v in routes_root.attrib.items():
            new_root.set(k, v)
        for elem in routes_root.findall('vType'):
            new_root.append(elem)
        for _, elem in person_elems:
            new_root.append(elem)

        routes_tree._setroot(new_root)
        routes_tree.write(routes_path)


    def add_homes(self, output_path, pedestrians):
        """Add pedestrians' initial home position in output trajectories.

        Params
        ------
        output_path : str
            File where output trajectories are stored.
        pedestrians : list of Pedestrian
            The collection of generated pedestrians.
        """

        new_output_path = output_path.replace('.xml', '_full.xml')

        # read file until first timestep entry is found
        with open(output_path) as in_file:
            with open(new_output_path, 'w') as out_file:
                found = False
                for line in in_file:
                    if not found and '<timestep' in line:
                        found = True

                        # first step, insert all pedestrians at home at time 0
                        out_file.write('\t<timestep time="0.00">\n')
                        for ped in pedestrians:

                            # get coords of home edge middle
                            shape = ped.home.getShape()
                            h_x, h_y = shape[math.trunc(len(shape)/2)]
                            out_file.write(
                                '\t\t<person id="ped{}_0"'.format(ped.id)
                                + ' x="{:.2f}" y="{:.2f}"'.format(h_x, h_y)
                                + ' angle="0.00" speed="0.00" pos="0.00"'
                                + ' edge="{}" slope="0.00"/>\n'.format(
                                    ped.home.getID()))
                        out_file.write('\t</timestep>\n' + line)

                    # otherwise just keep same text
                    else:
                        out_file.write(line)

        return new_output_path


    def get_trajectories(self, n, days, store_dir=None, geo_format=False,
        plot=False):
        """Generate trips, run SUMO simulation and get trajectory data.

        Params
        ------
        n : int
            The number of pedestrians to generate.
        days : int
            Total simulation duration in days.
        store_dir : str (optional, default: None)
            The directory to store files.
        geo_format : bool (optional, default: False - UTM)
            Whether to store results as UTM x/y or WSG lat/lon coords.
        plot : boolean (optional, default: False)
            Whether to plot active level and trip counts.
        """

        network_file = os.path.basename(self.network)

        # make sure store directory exists and contains network file
        if store_dir is not None:
            prefix = store_dir.rstrip("/") + "/"
            if not os.path.exists(store_dir):
                os.mkdir(store_dir)
            if not os.path.exists(prefix + network_file):
                copyfile(self.network, prefix + network_file)
        else:
            prefix = ""

        # setup file names and paths
        trips_file  = "{}_{}_trips.xml".format(n, days)
        routes_file = "{}_{}_routes.xml".format(n, days)
        output_file = "{}_{}_output.xml".format(n, days)
        config_file = "{}_{}_config.sumocfg".format(n, days)

        trips_path = prefix + trips_file
        routes_path = prefix + routes_file
        output_path = prefix + output_file

        # generate pedestrians
        pedestrians = self.generate_pedestrians(n)
        trips = self.generate_trips(pedestrians, days)
        self.store_trips(trips, trips_path)
        self.store_routes(trips_path, routes_path)

        # config and run SUMO
        print("Running SUMO")
        sumo = SUMO(network_file, routes_file, output_file, config_file,
            directory=store_dir, geo_format=geo_format, seed=self.seed,
            timestep=self.timestep_length)
        sumo.run()

        print("Inserting initial pedestrian position data...")
        new_output_path = self.add_homes(output_path, pedestrians)

        if plot:
            ActivityPlot.plot_levels(pedestrians, store_dir)
            ActivityPlot.plot_trips(pedestrians, trips, days, store_dir)
            ActivityPlot.plot_activity(pedestrians, trips, days, store_dir)
            ActivityPlot.plot_trip_distribution(pedestrians, trips, days, store_dir)

        return new_output_path
import random, math
import numpy as np


class Trip():
    """A representation of a single trip.

    Parameters
    ----------
    legs : list of sumolib.net.Path
        List of different paths of the trip.
    durations : list of float
        List of durations for each path in the trip.
    """
    
    def __init__(self, trip_id, ped_id, start_time, paths, times, durations,
        wait_times):
        
        self.trip_id = trip_id
        self.ped_id = ped_id
        self.start_time = start_time + times[0]
        self.paths = paths
        self.times = times
        self.durations = durations
        self.wait_times = wait_times


    def to_xml(self):
        """Convert this trip to xml."""

        string = "  <person id=\"ped{}\"".format(self.trip_id)
        string += (" depart=\"{}\" type=\"ped_pedestrian\">\n"
                    .format(self.start_time))

        # every path
        for t in range(len(self.paths)-1):
            string += ("     <walk from=\"{}\" to=\"{}\"/>\n"
                        .format(self.paths[t][0], self.paths[t][1]))
            string += ("     <stop lane=\"{}_0\" duration=\"{:.3f}\"/>\n"
                        .format(self.paths[t][1], self.wait_times[t]))

        # last bit
        string += ("     <walk from=\"{}\" to=\"{}\"/>\n"
                    .format(self.paths[-1][0], self.paths[-1][1]))
        string += ("  </person>\n")

        return string
            

class Pedestrian():
    """A representation of a pedestrian."""

    def __init__(self, id, home, pois, poi_distr, level, daily_travel_time):
        """Get a representation of a pedestrian.

        Parameters
        ----------
        id : str or int
            The id of the pedestrian.
        home : sumolib.net.Edge
            The home Edge of the pedestrian.
        pois : list of str
            The available points of interest.
        poi_distr : list of int, size == len(poi)
            The probability distribution of favorite pois.
        level : int
            The active level of the pedestrian.
        daily_travel_time : int
            The length of the day available for walking.
        """
        
        self.id = id
        self.home = home
        self.level = level
        self.trip_count = 0

        self.daily_travel_time = daily_travel_time 
        self.remaining_time = 0

        # remove home from pois if it exists
        pois = list(pois)
        poi_distr = list(poi_distr)
        if home in pois:
            pois.remove(home)

            # remove a probability and add it to another
            index = random.randrange(len(pois)-1)
            removed = poi_distr.pop(index)
            poi_distr[index+1] += removed

        self.pois = pois
        self.poi_distr = poi_distr


    def get_poi(self):
        """Get a single poi based on provided poi distribution."""

        # choices without replacement
        return np.random.choice(self.pois, p=self.poi_distr, replace=False)

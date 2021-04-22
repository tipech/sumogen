import matplotlib as mpl
from matplotlib import pyplot as plt
import numpy as np



class ActivityPlot():


    @staticmethod
    def plot_levels(pedestrians, store_dir=None):
        """Plot the pedestrian active level distribution."""

        cmap = mpl.cm.get_cmap('Blues')
        norm = mpl.colors.Normalize(vmin=-4, vmax=11)
        mpl.rcParams.update({'font.size': 16})
        
        levels = [ped.level for ped in pedestrians]
        level_counts = {l:levels.count(l) for l in levels}
        
        x_axis = sorted(level_counts.keys())
        y_axis = [v for k,v in sorted(level_counts.items())]
        y_axis = [100 * v/sum(y_axis) for v in y_axis]
        c_axis = [cmap(norm(c)) for c in range(len(x_axis))]

        plt.title("Active level distribution")
        plt.xlabel("level")
        plt.ylabel("population (%)")

        plt.bar(x_axis, y_axis, color=c_axis)
        plt.xticks(x_axis)

        plt.gcf().tight_layout()
        plt.gca().xaxis.set_tick_params(length=0)

        filename = "{}_levels.png".format(len(pedestrians))
        if store_dir is not None:
            filename = store_dir.rstrip("/") + "/" + filename
        plt.savefig(filename)
        plt.clf()


    @staticmethod
    def plot_trips(pedestrians, trips, days, store_dir=None):
        """Plot pedestrian trip counts per day, with stacked active levels."""
        
        # plot color and drawing parameters
        mpl.rcParams.update({'font.size': 16})
        cmap = mpl.cm.get_cmap('Blues')
        norm = mpl.colors.Normalize(vmin=-4, vmax=11)

        x_axis = range(days)
        ped_levels = {ped.id:ped.level for ped in pedestrians}
        # levels = len(set(ped_levels.values()))
        y_axes = {0: [0] * days}
        
        # get trips per level per time chunk
        for trip in trips:
            level = ped_levels[trip.ped_id]
            day = int(trip.start_time / (24*60*60))
            if level not in y_axes:
                y_axes[level] = [0] * days
            if day < days:
                y_axes[level][day] += 1

        # plot stacked bar plots
        plt.bar(x_axis, y_axes[0], color=cmap(norm(0)), width=1.0)
        bottom = y_axes[0]
        for l in range(1, len(y_axes)):
            if l in y_axes:
                plt.bar(x_axis, y_axes[l], bottom=bottom,
                    color=cmap(norm(l)), width=1.0)
                bottom = [bottom[i] + y_axes[l][i] for i in range(days)]

        # set x ticks to every 5 days
        ax = plt.gca()
        ax.xaxis.set_tick_params(length=0)
        plt.xticks(range(days), [1 + int(days*i/days) for i in range(days)])
        for index, label in enumerate(ax.xaxis.get_ticklabels()):
            if not(index == 0 or index + 1 in list(range(0, days + 5, 5))):
                label.set_visible(False)

        plt.title("Daily trips")
        plt.xlabel("day")
        plt.ylabel("# trips")
        ActivityPlot.add_colorbar(len(y_axes) - 1, cmap, norm)

        filename = "{}_trips.png".format(len(pedestrians))
        if store_dir is not None:
            filename = store_dir.rstrip("/") + "/" + filename
        plt.savefig(filename)
        plt.clf()


    @staticmethod
    def plot_activity(pedestrians, trips, days, store_dir=None):
        """Plot pedestrian trip durations, with stacked active levels."""
        
        # plot color and drawing parameters
        mpl.rcParams.update({'font.size': 16})
        cmap = mpl.cm.get_cmap('Blues')
        norm = mpl.colors.Normalize(vmin=-4, vmax=11)

        # split day into chunks, get appropriate axes
        resolution = 4*60*60 
        axis_length = int(days*24*60*60/resolution)
        x_axis = range(axis_length)
        ped_levels = {ped.id:ped.level for ped in pedestrians}
        y_axes = {0: [0] * axis_length}
        
        # get duration per level per time chunk for each trip
        for trip in trips:
            level = ped_levels[trip.ped_id]
            chunk = int(trip.start_time / resolution)
            if level not in y_axes:
                y_axes[level] = [0] * axis_length
            y_axes[level][chunk] += int(
                (sum(trip.durations) + sum(trip.wait_times))/(60*60))

        # average active time per hour in minutes
        for l in list(y_axes.keys()):
            y_axes[l] = [60 * (v/len(pedestrians) * (60*60/resolution))
                        for v in y_axes[l]]

        # plot stacked bar plots
        plt.bar(x_axis, y_axes[0], color=cmap(norm(0)), width=1.0)
        bottom = y_axes[0]
        for l in range(1, len(y_axes)):
            if l in y_axes:
                plt.bar(x_axis, y_axes[l], bottom=bottom,
                    color=cmap(norm(l)), width=1.0)
                bottom = [bottom[i]+y_axes[l][i] for i in range(axis_length)]

        # set x ticks to every 5 days, regardless of resolution
        ax = plt.gca()
        ax.xaxis.set_tick_params(length=0)
        plt.xticks(range(axis_length), [1 + int(days*i/axis_length)
                                        for i in range(axis_length)])
        for index, label in enumerate(ax.xaxis.get_ticklabels()):
            if not(index == 0 or index + 1 in
                list(range(0, axis_length + int(5 * axis_length/days),
                    int(5 * axis_length/days)))):
                label.set_visible(False)

        plt.title("Daily activity distribution")
        plt.xlabel("day")
        plt.ylabel("avg. active minutes per hour")
        ActivityPlot.add_colorbar(len(y_axes)-1, cmap, norm)

        filename = "{}_activity.png".format(len(pedestrians))
        if store_dir is not None:
            filename = store_dir.rstrip("/") + "/" + filename
        plt.savefig(filename)
        plt.clf()



    @staticmethod
    def plot_trip_distribution(pedestrians, trips, days, store_dir=None):
        """Plot pedestrian trip durations, with stacked active levels."""
        
        # plot color and drawing parameters
        mpl.rcParams.update({'font.size': 16})
        cmap = mpl.cm.get_cmap('Blues')
        norm = mpl.colors.Normalize(vmin=-4, vmax=11)

        # split day into chunks, get appropriate axes
        x_axis = range(len(pedestrians))
        ped_trips = {ped.id:0 for ped in pedestrians}
        ped_levels = {ped.id:ped.level for ped in pedestrians}
        max_level = max(ped_levels.values())

        # get trip count (or trip stops count, or average active hours)
        for trip in trips:
            ped_trips[trip.ped_id] += 1
            # ped_trips[trip.ped_id] += len(trip.paths)
            # ped_trips[trip.ped_id] += (sum(trip.durations)
            #                          + sum(trip.wait_times))/(days*60*60)

        y_axis = [count for pid, count in sorted(ped_trips.items(),
            key=lambda x: x[1], reverse=True)]
        c_axis = [cmap(norm(l)) for pid, l in sorted(ped_levels.items(),
            key=lambda x: ped_trips[x[0]], reverse=True)]

        plt.title("Pedestrian trip distribution")
        plt.xlabel("individual rank")
        plt.ylabel("# places visited")
        plt.bar(x_axis, y_axis, color=c_axis, width=1.0)
        plt.xticks([])
        plt.gca().xaxis.set_tick_params(length=0)
        ActivityPlot.add_colorbar(max_level, cmap, norm)

        filename = "{}_trip_distribution.png".format(len(pedestrians))
        if store_dir is not None:
            filename = store_dir.rstrip("/") + "/" + filename
        plt.savefig(filename)
        plt.clf()


    @staticmethod
    def add_colorbar(nr_levels, cmap, norm):
        """Plot a color bar next to the figure."""


        ax = plt.gca()
        fig = plt.gcf()

        bounds = np.linspace(0, nr_levels, nr_levels+1)
        cmaplist = [cmap(norm(l)) for l in range(nr_levels + 1)]
        cmap2 = mpl.colors.LinearSegmentedColormap.from_list(
            'Activity level colors', cmaplist, cmap.N)
        
        box = ax.get_position()
        box.x1 = box.x1 - 0.11
        ax.set_position(box)
        ax2 = fig.add_axes([0.86, 0.16, 0.03, 0.74])
        cb = mpl.colorbar.ColorbarBase(ax2, cmap=cmap2, norm=norm,
            spacing='proportional', ticks=bounds, boundaries=bounds, format='%1i')
        cb.set_label('activity level')


import subprocess, os, sys

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'.")



class SUMO():
    """Handles configuration and execution of SUMO binary."""


    def __init__(self, network_file, routes_file, output_file,
        config_file='config.sumocfg', directory=None, geo_format=False,
        timestep=1, seed=None):
        """Configure SUMO with provided parameters.

        Params
        ------
        network_file : str
            Traffic network file.
        routes_file : str
            Pedestrian routes file.
        output_file : str
            File to store output trajectories.
        config_file : str (optional, default: 'config.sumocfg')
            File to store simulation config.
        directory : str (optional, default: cwd)
            Working directory.
        geo_format : bool (optional, default: False - UTM)
            Whether to store results as UTM x/y or WSG lat/lon coords.
        timestep : int (optional, default: 1)
            Simulation timestep.
        seed : int (optional, default: None)
            Seed for the random number generated, random if none given.
        """

        # get working directory, config file
        if directory is None:
            directory = os.getcwd()
        self.directory = directory.rstrip("/") + "/"

        self.config_file = config_file

        # config setup
        config_xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<configuration'
            + ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            + ' xsi:noNamespaceSchemaLocation='
            + '"http://sumo.dlr.de/xsd/sumo-gui.exeConfiguration.xsd">\n\n')

        # network and routes files
        config_xml += ('<input>\n\t<net-file value="{}"/>\n'
            .format(network_file))
        config_xml += ('\t<route-files value="{}"/>\n</input>\n\n'
            .format(routes_file))

        # config timestep size, skip first timestep
        config_xml += ('<time>\n\t<step-length value="{}"/>'.format(timestep)
            +'\n\t<begin value="{}"/>\n</time>\n\n'.format(timestep))

        # output file, format and seed config
        config_xml += ('<output>\n\t<fcd-output value="{}"/>\n'
            .format(output_file))

        if geo_format:
            config_xml += '\t<fcd-output.geo value="true"/>\n'
        if seed is not None:
            config_xml += '\t<seed value="{}"/>\n'.format(seed)

        config_xml += '</output>\n\n'

        # final parameters
        config_xml += ('<processing>\n\t<ignore-route-errors value="true"/>'
            +'\n\t<pedestrian.model value="nonInteracting"/>\n'
            +'</processing>\n\n')
        config_xml += '</configuration>'

        # write config file
        with open(self.directory + config_file, "w") as file:
            file.write(config_xml)
        

    def run(self):
        """Run the simulation"""

        return subprocess.run(["sumo", self.config_file], cwd=self.directory)

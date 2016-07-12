#!/usr/bin/env python
"""Cassandra Stat, an IO Stat like program to monitor Cassandra."""
from __future__ import print_function
import requests
import argparse
import sys
from datetime import datetime
from copy import deepcopy
import time


class CassandraStat(object):
    """Continually poll a Cassandra instance for stats and output it to stdout.

    Once the cassandra stat object is instantiated it begins running until
    recieving a keyboard interrupt.
    """

    def __init__(
        self,
        host,
        header_rows,
        rate,
        show_system,
        show_keyspace,
        show_cfs,
        show_total,
        show_zeros,
        namespaces
    ):
        """
        Create a CassandraStat instance and begin running immediately.

        **Args:**
            host (str):
                Host and port to connect to, format http://HOST:PORT
            header_rows (int):
                How many rows should pass before a new header line is output.
                If this is 0 then only the first header will be printed, and if
                this is -1 then the top header row will not be printed.
            rate (int):
                How many seconds should pass between server polls.
            show_system (bool):
                Include system keyspaces and their related column families in
                the output.  The aggregation in "total" will include system
                keyspace entires as well.
            show_keyspace (bool):
                Show keyspace level output.
            show_cfs (bool):
                Show column family level output.
            show_total (bool):
                Show a row with overall total stats for the instance.
            show_zeros (bool):
                Show all namespaces that are set to be output regardless if
                there is no activity.
            namespaces (list<string>):
                list of keyspace or keysapce.cf names to be shown
        """
        self.host = host
        self.header_rows = header_rows
        self.rate = rate
        self.show_system = show_system
        self.show_keyspace = show_keyspace
        self.show_cfs = show_cfs
        self.show_zeros = show_zeros
        self.namespaces = namespaces
        self.show_total = show_total
        self.previous_data = {}
        self.current_data = {}
        # Note the display name must be unique amongst metrics or you will
        # encounter undocumented and unspecified behavior
        self.metrics = [
            {
                "metric_name": "ReadLatency",
                "metric_key": "Count",
                "display_name": "Reads",
                "sum": True,
                "diff": True,
                "nonzero": True
            },
            {
                "metric_name": "RangeLatency",
                "metric_key": "Count",
                "display_name": "Ranges",
                "sum": True,
                "diff": True,
                "nonzero": True
            },
            {
                "metric_name": "WriteLatency",
                "metric_key": "Count",
                "display_name": "Writes",
                "sum": True,
                "diff": True,
                "nonzero": True
            },
            {
                "metric_name": "ReadLatency",
                "metric_key": "99thPercentile",
                "display_name": "Reads (99%) ms"
            },
            {
                "metric_name": "RangeLatency",
                "metric_key": "99thPercentile",
                "display_name": "Ranges (99%) ms"
            },
            {
                "metric_name": "WriteLatency",
                "metric_key": "99thPercentile",
                "display_name": "Writes (99%) ms"
            },
            {
                "metric_name": "PendingCompactions",
                "metric_key": "Value",
                "display_name": "Compactions",
                "sum": True
            },
            {
                "metric_name": "PendingFlushes",
                "metric_key": "Count",
                "display_name": "Flushes",
                "sum": True
            },
            {
                "metric_name": "RowCacheMiss",
                "metric_key": "Count",
                "display_name": "Row Cache Misses",
                # "space": 18,
                "sum": True,
                "diff": True
            }
        ]
        self.run()

    def run(self):
        """Run the cassandra-stat process until a keyboard interrupt.

        **Args:**
            None

        **Returns:**
            None
        """
        cnt = 0
        if self.header_rows >= 0:
            self.printheaders()
        while True:
            if self.previous_data:
                cnt += 1
            time.sleep(self.rate)
            if cnt == self.header_rows:
                cnt = 1
                self.printheaders()
            self.printdata()
            self.previous_data = self.current_data

    def printheaders(self):
        """Print headers to stdout.

        **Args:**
            None

        **Returns:**
            None
        """
        headerstr = ""
        for metric in self.metrics:
            space = metric.get("space", len(metric["display_name"]) + 2)
            headerstr += metric["display_name"].center(space)
        headerstr += "time".center(12)
        headerstr += "ns"
        print(headerstr)

    def parsejmxkey(self, key):
        """Parse a JMX key into a list of dicts.

        **Args:**
            key (str):      JMX key of the format "uri:key1=value1,key2=value2"
        **Returns:**
            list<dict>:     List of dicts of the form {key1: value1}
        """
        kvs = key.split(":")[1]
        kvlist = kvs.split(",")
        retval = {}
        for kv in kvlist:
            split = kv.split("=")
            retval[split[0]] = split[1]
        return retval

    def fetch_and_update(self, data, name, keyname, internalname, sum=True):
        """Fetch a metric from JMX and include it in our data dictionary.

        The jolokia service has a get request made to it to read a metric that
        is passed in as name and keyname from the server.  The name may be
        WriteLatency and the keyname could be Count to retrieve the count of
        how many writes have occured.

        It will respond with a json of which the data is contained in the value
        field.  Therein is a list of dicts where the key is a jmx key of the
        form "uri:key1=value1,key2=value2" and the value is itself a dict of
        keyname (such as Count) to the actual value of the metric.

        The jmx key is parsed out by a different function to extract the
        namespace that the metric is acting on.  It uses the namespace, which
        is composed of <keyspace>.<columnfamily> as the key in the internal
        data dictionary that is passed in.  The internal data dict has the
        structure of
            {
                <namespace>: {
                    <internalname>: value
                }
            }
        and the corresponding namespace and internalname is updated with the
        value that is recieved from jmx.  If the sum flag is false then it
        will update the field in the data dict for the largest value, if it is
        sum then it will add the value to the namespace.

        **Args:**
            data (dict):
            name (str):
            keyname (str):
            internalname (str):
            sum (boolean, default=True):

        **Returns:**
            None
        """
        try:
            resp = requests.get(
                "{host}/jolokia/read/org.apache.cassandra.metrics:"
                "type=ColumnFamily,*,name={name}/{key}"
                .format(name=name, key=keyname, host=self.host)
            )
        except requests.exceptions.ConnectionError:
            print(
                "The application recieved a connection error, perhaps "
                "the ports are not open to the host specified or "
                "you do not have the jolokia agent installed and active. "
                "Please download the jolokia JVM agent jar file and insert "
                "JVM_OPTS=\"$JVM_OPTS -javaagent:PATH_TO_JOLOKIA_JAR.jar\" "
                "into your cassandra-env.sh file and restart cassandra."
            )
            sys.exit(1)
        if resp.json().get("error"):
            print(
                "ERROR the jolokia agent returned an error trying to access "
                "the following metric : "
                "org.apache.cassandra.metrics:type=ColumnFamily,*,"
                "name={name}/{key}".format(name=name, key=keyname)
            )
            return
        else:
            jmxdata = resp.json()["value"]
        for key, jmxobj in jmxdata.items():
            fields = self.parsejmxkey(key)

            # If there is no keyspace do not process the entry, this is some
            # internally aggregated value and we are doing custom aggregation
            if "keyspace" not in fields:
                continue

            # If the keyspace is a system keyspace skip processing unless
            # the show_system flag is true
            if(
                fields["keyspace"] in [
                    "system",
                    "system_keyspaces",
                    "system_auth"
                ] and not self.show_system
            ):
                continue

            full_namespace = "{ksp}.{cf}".format(
                ksp=fields["keyspace"],
                cf=fields["scope"]
            )

            # If the user has passed in a set of namespaces that we should be
            # restricted to then check if this namespace is in this restricted
            # set.  If not then we should not process it, if there are no
            # namespaces passed in by the user we should use all namespaces.
            if self.namespaces:
                include_namespace = False
                for passed_in_namespace in self.namespaces:
                    if "." in passed_in_namespace:
                        if passed_in_namespace == full_namespace:
                            include_namespace = True
                            break
                    else:
                        if passed_in_namespace == fields["keyspace"]:
                            include_namespace = True
                            break
                if not include_namespace:
                    continue

            # If the show_cfs flag is true then our namespace is the full
            # keyspace.columnfamily namespace
            # If the show_keyspace flag is true then the namespace we are
            # using will be just the keyspace
            # If neither flag is set we will only store things in totals
            if self.show_cfs:
                ns = full_namespace
            elif self.show_keyspace:
                ns = fields["keyspace"]
            else:
                ns = None

            if ns:
                if ns not in data:
                    data[ns] = {}
                if internalname not in data[ns]:
                    data[ns][internalname] = jmxobj[keyname]
                else:
                    if sum:
                        data[ns][internalname] += jmxobj[keyname]
                    elif data[ns][internalname] < jmxobj[keyname]:
                        data[ns][internalname] = jmxobj[keyname]

            if self.show_total:
                if internalname not in data["total"]:
                    data["total"][internalname] = jmxobj[keyname]
                else:
                    if sum:
                        data["total"][internalname] += jmxobj[keyname]
                    elif data["total"][internalname] < jmxobj[keyname]:
                        data["total"][internalname] = jmxobj[keyname]

    def getdata(self):
        """Get all data from jmx and construct a data dict.

        This constructs a data dict of the form
            {
                <namespace>: {
                    <internalname>: value
                }
            }
        for all the metrics that are output by cassandra-stat through
        repeated calls to fetch_and_update.

        **Args:**
            None

        **Returns:**
            dict:       the data dictionary, format is described above.
        """
        retval = {}
        if self.show_total:
            retval["total"] = {}

        for metric in self.metrics:
            self.fetch_and_update(
                data=retval,
                name=metric["metric_name"],
                keyname=metric["metric_key"],
                internalname=metric["display_name"],
                sum=metric.get("sum", False)
            )
        return retval

    def diffdata(self):
        """Find the difference in the state of Cassandra from the last iteration.

        This takes in two different data dictionaries, one from the last
        iteration and one from this iteration.  The process will take a
        difference of some of these metrics, others it will take the latest
        value, and it will return a new data dict that has the values that
        should be output to the user.

        **Args:**
            None

        **Returns:**
            dict:               data dict that contains the values to be output
        """
        retval = deepcopy(self.current_data)
        for ns, current_metric_data in self.current_data.items():
            # Iterate through all metrics that we are collecting
            for metric in self.metrics:
                # If the metric should have its difference taken then do so,
                # otherwise just report the most recent value
                if metric("diff"):
                    retval[ns][metric["display_name"]] = (
                        current_metric_data.get(metric["display_name"], 0) -
                        self.previous_data.get(ns, {}).get(
                            metric["display_name"], 0
                        )
                    )
                else:
                    retval[ns][metric["display_name"]] = (
                        current_metric_data.get(metric["display_name"], 0)
                    )
        return retval

    def printdataline(self, data):
        """Print to stdout a single line of data.

        **Args:**
            data (dict):        Data dict that is the output of the diffdata
                                function, see getdata function for structure.

        **Returns:**
            None
        """
        # Are there any metrics that are nonzero metrics, which means if all of
        # these metrics are zero then we don't want to show the namespace
        nonzero_fields = []
        for metric in self.metrics:
            if metric.get("nonzero"):
                nonzero_fields.append(metric)

        number_of_printed_ns = 0
        for ns, metric_data in data.items():
            # If we are showing zeros then it doesn't matter if the metrics
            # are all zero or not because we are showing them regardless.  If
            # there are no fields designated as nonzero then we show all rows
            # as well.

            # If there are nonzero fields then we should check that at least
            # one of the metrics is nonzero
            ns_has_nonzero = not len(nonzero_fields) or self.show_zeros
            if not ns_has_nonzero:
                for metric in nonzero_fields:
                    if metric_data.get(metric["display_name"]):
                        ns_has_nonzero = True
                        break

            # If we have set no_total to true then we want to hide the total ns
            is_total = (ns == "total")
            if self.no_total:
                is_total = False

            # Displaying the row to the user if it passes our criteria
            if ns_has_nonzero or is_total:
                datastr = ""
                for metric in self.metrics:
                    space = metric.get(
                        "space", len(metric["display_name"]) + 2
                    )
                    datastr += str(
                        metric_data.get(metric["display_name"], 0)
                    ).center(space)
                datastr += datetime.now().strftime("%H:%M:%S").center(12)
                datastr += ns
                number_of_printed_ns += 1
                print(datastr)
        # If there are multiple namespaces are printed then we should
        # put a new line in between each block of namespaces
        if len(number_of_printed_ns) > 1:
            print("\n")

    def printdata(self):
        """Fetch a new iteration of data and print data to stout.

        **Args:**
            None

        **Returns:**
            None
        """
        self.current_data = self.getdata()
        if self.previous_data:
            self.printdataline(self.diffdata())


def parse_args():
    """Parse command line arguments.

    **Args:**
        None

    **Returns:**
        Namespace object that represents the parsed command line
    """
    parser = argparse.ArgumentParser(
        description=(
            'Cassandra-stat tool for live monitoring of Cassandra traffic.'
        )
    )
    exclusion_group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '--host',
        dest='host',
        default="http://localhost:8778",
        help='Host and port to connect to, format http://HOST:PORT.'
    )
    exclusion_group.add_argument(
        '--header_rows',
        dest='header_rows',
        default=10,
        type=int,
        help=(
            'How many rows should pass before a new header line is output.  '
            'If this is 0 then only the first header will be printed, and if '
            'this is -1 then the top header row will not be printed.'
        )
    )
    parser.add_argument(
        '--rate',
        dest='rate',
        default=1,
        type=int,
        help='How many seconds should pass between server polls.'
    )
    parser.add_argument(
        '--show_system',
        dest='show_system',
        default=False,
        action="store_true",
        help=(
            'Include system keyspaces and their related column families in '
            'the output.  The aggregation in "total" will include system '
            'keyspace entires as well.'
        )
    )
    parser.add_argument(
        '--show_keyspace',
        dest='show_keyspace',
        default=False,
        action="store_true",
        help='Show keyspace level output.'
    )
    parser.add_argument(
        '--show_cfs',
        dest='show_cfs',
        default=False,
        action="store_true",
        help='Show <keyspace>.<columnfamily> level output.'
    )
    parser.add_argument(
        '--show_zeros',
        dest='show_zeros',
        default=False,
        action="store_true",
        help=(
            'Show all namespaces that are set to be output regardless if '
            'there is no activity.'
        )
    )
    parser.add_argument(
        '--no_total',
        dest='no_total',
        default=False,
        action="store_true",
        help=(
            'Suppress output of total aggregation. This may have the effect '
            'of having no output when there is no traffic in the database.'
        )
    )
    parser.add_argument(
        '--namespaces',
        dest='namespaces',
        default="",
        help=(
            'Comma separated list of namespaces to process and show.  To show '
            'an entire keyspace then use the keyspace name as an entry, and '
            'to show only a column family then add <keyspace>.<columnfamily> '
            'to the list.  This flag can result in suprsing behavior if you '
            'are not careful so please see the README file for more.'
        )
    )
    return parser.parse_args()


def main():
    """Create an instance of CassandraStat and run until interrupt.

    **Args:**
        None

    **Returns:**
        None
    """
    args = parse_args()
    namespaces = []
    if args.namespaces:
        namespaces = args.namespaces.split(",")

    CassandraStat(
        host=args.host,
        header_rows=args.header_rows,
        rate=args.rate,
        show_system=args.show_system,
        show_keyspace=args.show_keyspace,
        show_cfs=args.show_cfs,
        show_total=(not args.no_total),
        show_zeros=args.show_zeros,
        namespaces=namespaces
    )


if __name__ == "__main__":
    main()

 cassandra-toolbox
=========================

A suite of tools for Cassandra - A highly scalable distributed NoSQL datastore.

These are a set of monitoring and analysis tools that were initially developed at Knewton in order to introspect behavior and performance of the Cassandra clusters at knewton.  These scripts are designed to run locally or remotely against a cassandra cluster.  Just install this into your virtual environment and go for it.

**Be aware that these scripts do cause some load on the target server which can impact your performance.  Nothing comes without a price.**

Installation
============

It is preferable to create a virtual environment to install these tools into

    pip install virtualenv
    virtualenv /path/to/your/virtualenv
    source /path/to/your/virtualenv/bin/activate

To install the project you can clone this repo and install it directly into your virtual environment, this would get you the latest code

    git clone git@github.com:Knewton/cassandra-toolbox.git
    cd cassandra-toolbox
    ./setup.py install

You can also directly install our package from pip

    pip install cassandra-toolbox


Usage
=====

This package consists of several scripts that get installed as executables into the environment that the package is in.  Each script does something different and is described independently below.

cassandra-stat
----------------

The cassandra-stat tool shows a real-time feed of how many operations have gone through Cassandra as reported by the JMX interface that is exposed.  Many people pump this information through Graphite or another data collector which is a good idea so you can visualize and store the data.  However these systems usually poll every minute and can lag behind events.  This allows you to see to the second what is occuring on the system in a manner similar to iostat.

This script interfaces with the jolokia jmx-http bridge which must be attached to your Cassandra instances that you plan to run cassandra-stat against.  This is very easy however and not intrustive to Cassandra.

Installing Jolokia is painless.  You first download the JVM agent from their website https://jolokia.org/download.html .  Then you modify your `cassandra-env.sh` file to include the following line:
    JVM_OPTS="$JVM_OPTS -javaagent:<Path To Jolokia JVM Agent Jar>.jar"
A restart of the Cassandra instance is required after this modification.

To use cassandra-stat you only need to execute the following local to the Cassandra instance you wish to monitor.  You must have activated the virtual environment that cassandra-toolbox is installed into if you have installed the pacakge into a virtual environment.

    $cassandra-stat

The output will look similar to the following:

    Reads     Ranges    Writes    Reads (99%) ms   Ranges (99%) ms   Writes (99%) ms   Compactions     Flushes    Row Cache Misses     Time    ns
      1         0        111          91.462            68.81            17.4               0             0              0           20:15:36  total
      2         4        113           91.4             68.30            17.98              0             0              0           20:15:37  total
      0         0        117           91.4             68.30            17.17              0             0              0           20:15:38  total
      0         0         72           91.4             68.30            17.34              0             0              0           20:15:39  total
      0         2         69           91.4             68.30            17.3               0             0              0           20:15:40  total

The fields that are output are as follows:

 * Reads:               Number of reads since the last line was reported
 * Ranges:              Number of range queries since the last line was reported
 * Writes:              Number of writes (updates/insertions/deletions) since the last line was reported
 * Reads (99%):         99th percentile latency in reads given in milliseconds
 * Ranges (99%):        99th percentile latency in range queries given in milliseconds
 * Writes (99%):        99th percentile latency in writes (updates/insertions/deletions) given in milliseconds
 * Compactions:         Number of pending compactions
 * Flushes :            Number of memtable flushes that are in progress
 * Row Cache Misses:    Number of row cache misses that have occured since the last line was reported
 * time:                Time in HH:MM:SS that the line was recorded at
 * ns:                  Namespace that the statistic is output for.  This can be "total" which is a sum for all keyspaces, `<keyspace>` which is a sum of all column families inside that keyspace, or `<keyspace>.<columnfamily>` which is the most granular output

If a namespace has no traffic, that is if there are 0 reads, range queries, or writes reported for that namespace then the namespace will not be output to the screen with the exception of "total" which will always be output.  Note that some of the statistics are differences with the previous line so the absolute numbers can vary depending on the rate that is chosen (this is configurable, see below).  Additionally the 99 percentile outputs are for a moving average that is generated internally by the Cassandra metric libraries so they are not representative of the 99th percentile at that instant.  Any aggregate level metrics (total or keyspace level metrics) will show the highest 99th percentile latency.  Aggregates for other metrics are summations of the constituent column families.  By default system keyspaces are not included in these aggregations, but this is configurable.

Configurations are set by command line flags, these can be accessed by running `cassandra-stat --help`:

  * --header_rows int:
  	* An integer of how many rows should pass before a new header line is output.  If this is 0 then only the first header will be printed, and if this is -1 then the top header row will not be printed.  Default 10.
  * --rate int:
  	* How many seconds should pass between server polls.  Default 1.
  * --show_system:
	* Include system keyspaces and their related column families in the output.  The aggregation in "total" will include system keyspace entires as well, which is not the default behavior.
  * --host string:
	* The http://HOST:PORT that this script should connect to.  Default http://localhost:8778.
  * --show_keyspaces:
	* Set this flag in order to show keyspace level output.
  * --show_cfs:
	* Set this flag to show `<keyspace>.<columnfamily>` level output.
  * --no_total:
	* Set this flag to suppress output of the aggregated total.  This may have the effect of having no output when there is no traffic in the database.
  * --show_zeros:
	* Show all namespaces that are set to be output regardless if there is no activity.
  * --namespaces string:
  	* Comma separated list of namespaces to process and show.  To show an entire keyspace then use the keyspace name as an entry, and to show only a column family then add `<keyspace>.<columnfamily>` to the list.  For example `--namespaces keyspace1,keyspace2.test1` would show all column families from keyspace1 and only the test1 column family from keyspace2.  Note that there can be strange behaviors with this flag as other flags.  Adding a system keyspace to this flag will have no effect unless the `--show_system` flag is also included.  Adding namespaces to this flag will change what namespaces are included in the total for aggregations but these namespaces will not be printed out if the `--show_keyspaces` or `--show_cfs` flags are not included.  For example `--namespaces keyspace1,keyspace2.test1 --show_keyspaces` would output an entry for `total`, `keyspace1`, and `keyspace2` where `total` will be the aggregate of all column families in keyspace1 as well as the column family test1 in keyspace2, `keyspace1` will be the aggregate of all column families within it, and `keyspace2` will be the aggregate of only the column family `test1`.  If you are using this flag and show_system then you must include which system keyspaces you wish to include, they will not be included by default if using the namespaces flag.

cassandra-tracing
-----------------
This script facilitates analysis of Cassandra tracing data, which on its own is difficult to draw conclusions from.  Tracing is very useful to look at individual CQL queries in the cqlsh shell, however to get a better idea of your system's behavior it is often useful to sample a percentage of queries, trace them, and save these traces for later.  Cassandra makes this easy to do with nodetool.  You can use the following to set the probability that any cql query (that is coordinated by the cassandra node local to this command) is traced to 0.1%.

	$nodetool settraceprobability 0.001

Note that a value of 1 means every query will be traced.  A trace logs many lines for every query so be careful of setting this value very high.  It is possible that tracing less than 5% of all queries can result in a write workload which is equal in number to the load which it is tracing.

To use cassandra-tracing you only need to execute the following local to the Cassandra instance you wish to investigate the tracing logs of.  You must have activated the virtual environment that cassandra-toolbox is installed into if you have installed the pacakge into a virtual environment.

    $cassandra-tracing `hostname -I`


The output will look similar to the following:

	$ cassandra-tracing `hostname -I `
	100% Complete: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX|100

	Total skipped due to null duration:	0
	Total skipped due to error:	0

	175 sessions satisfying criteria.
	Showing 100 longest running results.
	               Session Id                Duration (microsecs)    Max Tombstones     Total Tombstones    Flags            Time Started         Query
	  bedd77a0-159e-11e6-af1d-5b2aec1d0944          19696                  32                  32                     2016-05-09T04:30:23.259000  SELECT * FROM system.schema_columnfamilies
	  be941af0-1801-11e6-9deb-25e4276011e4          20569                  0                   0                      2016-05-12T05:24:05.280000  Executing single-partition query on ColumnFamilyA
	  b4c924a0-1565-11e6-af1d-5b2aec1d0944          20905                  32                  32                     2016-05-08T21:42:05.041000  SELECT * FROM system.schema_columnfamilies
	  fdf6fda0-174a-11e6-ace9-39442dcd207a          21056                  0                   0                      2016-05-11T07:35:53.724000  Executing single-partition query on ColumnFamilyB
	  c5f24e80-1751-11e6-af1d-5b2aec1d0944          21397                  0                   0                      2016-05-11T08:24:26.216000  Executing single-partition query on ColumnFamilyB
	  f7670600-183b-11e6-af1d-5b2aec1d0944          21992                  0                   0                      2016-05-12T12:20:51.425000  Executing single-partition query on ColumnFamilyC

The output displays the following information, sorted by duration:

  * Session ID
  * Duration in microseconds
  * Max number of tombstones encountered on a single session
  * Total tombstones encountered
  * Flags signifying special behavior, according to the legend:
      * R = read repair
      * T = timeout
      * I = index used
  * Starting timestamp of the session (hidden in slim mode)
  * CQL query or inferred query fragment (hidden in slim mode)

The Session Id can be used to introspect specific queries (which are logged as a session) in cqlsh yourself, by querying for the session id in the events table of the system_tracing keyspace.

	$ cqlsh `hostname -I`
	Connected to cassandra at 172.ip.ip.ip:9042.
	[cqlsh 5.0.1 | Cassandra 2.1.11 | CQL spec 3.2.1 | Native protocol v3]
	Use HELP for help.
	cqlsh> use system_traces;
	cqlsh:system_traces> select * from events WHERE session_id=bedd77a0-159e-11e6-af1d-5b2aec1d0944;

	 session_id                           | event_id                             | activity                                                                                         | source       | source_elapsed | thread
	--------------------------------------+--------------------------------------+--------------------------------------------------------------------------------------------------+--------------+----------------+---------------------
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bedd9eb0-159e-11e6-af1d-5b2aec1d0944 |                                               Parsing SELECT * FROM system.schema_columnfamilies | 172.ip.ip.ip |             21 | SharedPool-Worker-2
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | beddecd0-159e-11e6-af1d-5b2aec1d0944 |                                                                              Preparing statement | 172.ip.ip.ip |             31 | SharedPool-Worker-2
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bede13e0-159e-11e6-af1d-5b2aec1d0944 |                                                                        Computing ranges to query | 172.ip.ip.ip |             73 | SharedPool-Worker-2
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bede3af0-159e-11e6-af1d-5b2aec1d0944 | Submitting range requests on 1 ranges with a concurrency of 1 (22.37143 rows per range expected) | 172.ip.ip.ip |             88 | SharedPool-Worker-2
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bede6200-159e-11e6-af1d-5b2aec1d0944 |                                          Submitted 1 concurrent range requests covering 1 ranges | 172.ip.ip.ip |             96 | SharedPool-Worker-2
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | beded730-159e-11e6-af1d-5b2aec1d0944 |                                      Executing seq scan across 3 sstables for [min(-1), min(-1)] | 172.ip.ip.ip |            382 | SharedPool-Worker-4
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bedefe40-159e-11e6-af1d-5b2aec1d0944 |                                                                Read 7 live and 0 tombstone cells | 172.ip.ip.ip |           2057 | SharedPool-Worker-4
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bedf2550-159e-11e6-af1d-5b2aec1d0944 |                                                                Read 2 live and 0 tombstone cells | 172.ip.ip.ip |           2495 | SharedPool-Worker-4
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bedf7370-159e-11e6-af1d-5b2aec1d0944 |                                                                Read 1 live and 0 tombstone cells | 172.ip.ip.ip |           3066 | SharedPool-Worker-4
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bee00fb0-159e-11e6-af1d-5b2aec1d0944 |                                                              Read 17 live and 32 tombstone cells | 172.ip.ip.ip |          16892 | SharedPool-Worker-4
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bee05dd0-159e-11e6-af1d-5b2aec1d0944 |                                                                Read 7 live and 0 tombstone cells | 172.ip.ip.ip |          18757 | SharedPool-Worker-4
	 bedd77a0-159e-11e6-af1d-5b2aec1d0944 | bee084e0-159e-11e6-af1d-5b2aec1d0944 |                                                                     Scanned 5 rows and matched 5 | 172.ip.ip.ip |          19172 | SharedPool-Worker-4

The results from `cassandra-tracing` can be limited by thresholds on both duration and tombstones, and by and a result cap. The result cap gathers the same number of results but caps the display.  When limited results are displayed the results displayed are always the longest duration events.

Regardless of limiting mechanisms, note that full table scans must be done on the `sessions` and `events` tables in the `system_traces` keyspace.

Configurations are set by command line flags, these can be accessed by running `cassandra-tracing --help`:

  * node_ip:
	* Specify ip of the node being queried
  * --tombstoneThreshold int:
	* Show only sessions who read tombstones equal to or greater than this threshold.  Default 0.
  * --time int:
	* Show only sessions that took longer than this threshold in microseconds.  Default 10000 (10ms).
  * --resultCap int:
	* Maximum number of results to print out. To print all results, use 0.  Default 100.
  * --slim:
  	* Enable slim mode, where the query and time started are suppressed in the output.

Supported Python Versions
=========================

Python 2.7 and Python 3.4+ are supported.

Licenses
========

The cassandra-toolbox pacakge is licensed under the MIT license.

Issues
======

Please report any bugs or requests that you have using the GitHub issue tracker!

Authors
=======

* Dr. Jeffrey Berger
* Dr. Joshua Wickman
* Carlos Monroy Nieblas

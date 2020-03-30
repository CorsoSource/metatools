# Metatools for Ignition
### _Tools to build tools with_
The following is an eclectic collection of functions, classes, and settings that make it easier to do specific tasks in Ignition. Each was built to assist a larger goal and are handy to have around, a means to an end. Many focus on introspection - allowing code to look at itself (and by extension _you_).

If you find an issues, bugs, failings, or disappointments - file an issue! Feature requests are appreciated, and pull requests triply so! Any modifications submitted will be called out and the script file will be updated with a `__credits__` listing with your name (plus, it'll be tracked by Github).

## Example Usage (pretty printing)

Of all the scripts, the pretty printing functions are probably the most handy. Here's an example of how to use it, as seen from the Ignition script console:

```python
>>> some_dataset = shared.tools.examples.simpleDataset
>>> from shared.tools.pretty import *
>>> p(some_dataset)
"some_dataset" <DataSet> of 3 elements and 3 columns
====================================================
          a                     |  b                     |  c                    
           <java.lang.Integer>  |   <java.lang.Integer>  |   <java.lang.Integer> 
---------------------------------------------------------------------------------
   0 |                        1 |                      2 |                      3
   1 |                        4 |                      5 |                      6
   2 |                        7 |                      8 |                      9

>>> pdir(p)
  Properties of "p" <'function'>
  ================================
  (o, indent='  ', listLimit=42, ellipsisLimit=80, directPrint=True)
  --------------------------------------------------------------------
  Pretty print objects. This helps make lists, dicts, and other things easier to understand.
  Handy for quickly looking at datasets and lists of lists, too, since it aligns columns.   

  Attribute         Repr                                                                                                                         <Type>       
  -------------     ------------------------------------------------------------------------------------------------------------------------     -----------  
  func_closure      None                                                                                                                         NoneType     
  func_code         <code object p at 0x2, file "<module:shared.tools.pretty>", line 181>                                                        tablecode    
  func_defaults     ('  ', 42, 80, True)                                                                                                         tuple        
  func_dict         {}                                                                                                                           dict         
  func_doc          'Pretty print objects. This helps make lists, dicts, and other things easier to understand.\n\tHandy for quickly loo...      str          
  func_globals      {'shared': <app package shared at 3>, 'JavaException': <type 'java.lang.Exception'>, '__copyright__': 'Copyright (C)...      dict         
  func_name         'p'                                                                                                                          str      
>>> pdir(some_dataset)
  Properties of "some_dataset" <'com.inductiveautomation.ignition.common.BasicDataset'>
  =======================================================================================
  The most base type

  Attribute                Repr                                                                                                                         <Type>                   
  --------------------     ------------------------------------------------------------------------------------------------------------------------     -----------------------  
  asXML                    u'H4sIAAAAAAAAALOxr8jNUShLLSrOzM+zVTLUM1BSSM1Lzk/JzEu3VQoNcdO1ULK34+WySSm2s0nO\nz7GzSbEztNFPAdEmUNocTOuDZaFKjKBSplDa...      unicode                  
  binarySearch             (<int>, <java.lang.Object>)                                                                                                  instancemethod           
  bulkQualityCodes         None                                                                                                                         NoneType                 
  class                                                                                                                                                                          
  columnContainsNulls      (<int>)                                                                                                                      instancemethod           
  columnCount              3                                                                                                                            int                      
  columnNames              [a, b, c]                                                                                                                    java.util.Collections    
  columnTypes              [class java.lang.Integer, class java.lang.Integer, class java.lang.Integer]                                                  java.util.Collections    
  data                     array([Ljava.lang.Object;, [array(java.lang.Object, [1, 4, 7]), array(java.lang.Object, [2, 5, 8]), array(java.lang....      array.array              
  dataDirectly             n/a                                                                                                                          write-only attr          
  datasetContainsNulls     ()                                                                                                                           instancemethod           
  equals                   (<java.lang.Object>)                                                                                                         instancemethod           
  getAsXML                 ()                                                                                                                           instancemethod           
  getBulkQualityCodes      ()                                                                                                                           instancemethod           
  getClass                 ()                                                                                                                           instancemethod           
  getColumnAsList          (<int>)                                                                                                                      instancemethod           
  getColumnCount           ()                                                                                                                           instancemethod           
  getColumnIndex           (<java.lang.String>)                                                                                                         instancemethod           
  getColumnName            (<int>)                                                                                                                      instancemethod           
  getColumnNames           ()                                                                                                                           instancemethod           
  getColumnType            (<int>)                                                                                                                      instancemethod           
  getColumnTypes           ()                                                                                                                           instancemethod           
  getData                  ()                                                                                                                           instancemethod           
  getPrimitiveValueAt      (<int>, <int>)                                                                                                               instancemethod           
  getQualityAt             (<int>, <int>)                                                                                                               instancemethod           
  getRowCount              ()                                                                                                                           instancemethod           
  getValueAt               (<int>, <int>) -OR- (<int>, <java.lang.String>)                                                                              instancemethod           
  hashCode                 ()                                                                                                                           instancemethod           
  notify                   ()                                                                                                                           instancemethod           
  notifyAll                ()                                                                                                                           instancemethod           
  rowCount                 3                                                                                                                            int                      
  setAllDirectly           (<java.util.List>, <java.util.List>, <[[Ljava.lang.Object;>)                                                                 instancemethod           
  setColumnNames           (<java.util.List>)                                                                                                           instancemethod           
  setColumnTypes           (<java.util.List>)                                                                                                           instancemethod           
  setData                  (<[[Ljava.lang.Object;>)                                                                                                     instancemethod           
  setDataDirectly          (<[[Ljava.lang.Object;>)                                                                                                     instancemethod           
  setFromXML               (<java.util.List>, <java.util.List>, <java.lang.String>, <int>)                                                              instancemethod           
  setValueAt               (<int>, <int>, <java.lang.Object>)                                                                                           instancemethod           
  toString                 ()                                                                                                                           instancemethod           
  wait                     () -OR- (<long>) -OR- (<long>, <int>)                                                                                        instancemethod           

```

One of the neat tricks some of the functions ~~ab~~use is how aware of their surroundings they are. Note that the `p(some_dataset)` calls out the name of the _variable_ itself, and that `pdir(p)` lists out the arguments of the function. Note that `pdir(some_dataset)` not only lists all the attributes, but the signatures of functions and the values of attributes, _even though it is a Java object_.

## Testing

Tests are currently written for Python's built in `unittest` and `doctest` libraries. See the `test/shared/tools` folder for coverage.

#### Disclaimer
While **I** use the code here semi-regularly, do take a moment to understand any code you plan to use in production! This is always a good idea, but some of the scripts operate on Python magic. Some are extremely handy, like scope injection used in the `Logger` to make Python3-style string formatting. Others like `@async` gently abuse notation for convenience. And others like `Trap` violently abuse the Python's internal runtime machinery.

All the code is safe. All applications of it are _not_.

That out of the way, here's the handy stuff! 

## Scripts (in alphabetical order)
Here's an overview of each script with a little about what each function has to offer.

### compat (Ignition 7 only)

Jython 2.5 (Ignition 7) does not have all the builtin features normally expected. Python 2.6 brought in a large number of important changes, some of which are not obviously missing. These are some of the more commonly backported/monkey patched details that seem to come up.

Worst offender? `next`. Boy howdy to a lot of programs expect that to just exist.

```python
>>> OrderedDict((key,value) for key,value in zip(list('asdf'),range(4)))
OrderedDict([('a', 0), ('s', 1), ('d', 2), ('f', 3)])
```

### data
These functions make it easier to convert to and from the `DataSet` Java object. Immutable and fast, DataSet virtues are also a _chore_ to work with when so much of Python is geared around transparent iteration and mutability. 

### dump

To better analyze Ignition projects, the `dump` scripts can be used to trawl resources to disk. Typically, the files on disk are base-64 encoded gzip dumps of the XML generated. Scripts here help work around that to get the fine-grained XML detail for resources.

My typical use for this is performing a diff between projects. By consuming the XML and sorting & flattening objects, a [typical diff algorithm](https://docs.python.org/2.7/library/difflib.html) can be used to compare, well, almost anything. The detail is _extremely_ high, though, so beware the siren song of excessive depth and filter judiciously; otherwise you may find even trivial projects suffer from thousands of minor, inconsequential differences. (Careful and extensive filtering is the secret sauce to making sense of it all, and frankly it would be a problem regardless of the output, be it XML, JSON, or binary.)

It will not work on all resources. Please raise an issue if you find a resource that is not properly extracted; it may not be obviously fixable, but it's usually worth inspecting. 

 * `dumpProject` runs over the full currently-loaded project in the Ignition Designer and places the trawled output in the given directory on disk.
 * `getResources` is a more targeted function that will return only a certain class of object.
 * `serializeToXML` will (if easily possible) return the string the Java serializer for an object type generates.

### easing

Handy port of the easing functions from Javascript. If you need to make transitions, this is a nice way to smooth them out and look more natural.

### enum

The [enum](https://docs.python.org/3/library/enum.html) type doesn't get added to Python until version 3.4, but there's a use for this very specific type of object. Subclassing `Enum` will effectively create a singleton class whose elements may be used transparently as their values, but can be checked against as an enumeration.

For example, take the following arbitrary enumeration:
```python
from shared.tools.enum import Enum

class ArbFlags(Enum):
	NUMBER_1 = 1
	NUMBER_2 = 2
	Fourth = 4
	SomeString = 'This is a string.'
```
Note that the numbers may be referenced directly by name...
```python
>>> ArbFlags.NUMBER_1
<ArbFlags.NUMBER_1 1>
>>> ArbFlags.NUMBER_1 + 3
4
```
But behave exactly as their type...
```python
>>> ArbFlags.NUMBER_1 == 1
True
>>> ArbFlags.NUMBER_1 is 1
False
>>> ArbFlags.NUMBER_1 + 3 == ArbFlags.Fourth
True
>>> (1+3) is 4
True
>>> ArbFlags.NUMBER_1 + 3 is ArbFlags.Fourth
False
```
The having something act as its value while _being distinguishable_ from that value is what makes enumerations special.

### examples

For testing purposes, it's helpful to not need to constantly redefine things. In code examples (as already seen) these can be called upon to provide a repeatable/demonstratable input. Plus, they're used by the tests.

### logging

Logging in Ignition comes in many flavors and scenarios. And yet, there are a few caveats. Can't use `system.util.getLogger` effectively in the script console, defining loggers and their contexts can be verbose, and getting clients to log to the gateway is occasionally super helpful. This logging class lets you put as little or as much effort into this as you'd like. 

In general, simply import `Logger` and instantiate it when you want to use it. 
```python
Logger().debug('These words will be logged.)
```
You may use one of the following canonical logging levels (what the Java wrapper uses):
`trace` `debug` `info` `warn` `error` `log` (for whatever's set as default)

When created, the logger will inspect its calling scope and attempt to make sense of where it is. Currently, it can detect the following automatically:
 * **Script** console (previously the Script Playground) - it will `print` instead of use the Java logger.
 * **Module** scripts - it will name itself after the script's module, like `shared.tools.meta`
 * **Tags** - it will name itself as a `[TAG PROVIDER] Tag Change Event` and prefix all logs with the tag's path
 * **Perspective** - It will name itself after the Perspective client's ID and prefix the log with the calling component's path (if possible)
 * **Clients** - it will name itself after the Vision client's ID and prefix the log with the calling component's path.
 * **WebDev** - it will name itself `[PROJECT NAME] WebDev` and prefix logs with the event name, like `[GET endpoints/submit]`
 * **Unknown** - it will just call itself `Logger`. Nothing otherwise interesting.

> Note: logging from the Client context requires that a message handler is set up. The handler is provided, though - just create a message handler named whatever is named in:
>  * `VISION_CLIENT_MESSAGE_HANDLER`
>  * `PERSPECTIVE_SESSION_MESSAGE_HANDLER`
>  
>  with the following code
> ```python
> from shared.tools.logging import Logger
>		Logger.messageHandler(payload)
> ```
> 
The `Logger` class will look back into its calling scope to figure out context. That allows it to do some helpful string work for you.  The following are all equivalent (assuming there's a variable `x` that is an `integer`): 
 * `Logger().debug('The variable x is currently %d' % x)`
 * `Logger().debug('The variable x is currently %(ecks)d', ecks=x)`
 * `Logger().debug('The variable x is currently %(x)d')`

### meta

These are functions that dig into the Python and Ignition context. Most have trivial defaults and are easy to use. Just be careful when using them - they are meant for ad hoc introspection and _not_ constant use under production. They are not _efficient_ but rather _handy_.

### overwatch

The `Overwatch` class is a wrapper to simplify building your own debugger. Because it will execute on whatever provided events, it is possible to react to deeply detailed contexts, but it also means that it will **really** slow down execution. (Generally in a troubleshooting scenario this is fine, but understand that this causes additional code to be executed every. single. call/line/return/exception.) 

Configured correctly, it could even act as a `Trap` and behave as a just-in-time `try`/`except` clause for code _you can't touch_.

By default this will NOT run outside of the Vision Designer context.

### pretty

Print things in an easy to read way! Ever `print someList` and had it dump so many things you couldn't even scroll to the end? Hate having lists of lists be so hard to read because the columns don't line up? Want to `dir` all the things but can't stand mere _names_ of things? Wish you could print nested objects without getting confused?

Then `p` and `pdir` are for you. See the example at the start of this for how it works. Generally just take whatever you've got and jam it in the function.

### thread

The `@async` decorator is a simple, easy way to make something asynchronous (run in its own thread) while keeping the boilerplate to a minimum. Call it with a number to set it to run itself after a pause, like this will run `foo` in half a second:
```python
@async(0.5)
def foo(x):
	print x
``` 
Note also that the function returns the thread handle itself. See the docstring for the decorator for more details on how that works.

### timing

If you need to run something in a loop, but don't want to use a timer component, these classes should help. 
 * `AtLeastThisDelay` will pause execution after it's run until at least the given delay has passed. Handy for rate limiting things like REST calls.
 * `EveryFixedBeat` will execute every given time period, but if execution takes too long it will skip and wait for the next beat. Use this for when you need evenly spaced events.
 * `EveryFixedDelay` will execute each iteration after the given delay. Use this when you need at least a certain delay between iterations.

> Note: Both `EveryFixedBeat` and `EveryFixedDelay` behave as though they were called with `enumerate` (returning **both** the iteration number and the last iteration's time each loop), but `EveryFixedBeat` may skip iterations if the loop takes too long.  

### trap 

WARNING: This is under development and should NOT be used in production. This is still being ported into Ignition's Jython execution environment.

`Trap` watches execution and does something when it sees a scenario come up (typically dropping into debug mode, if possible).

### venv

A fairly simple way to create an ad hoc virtual environment. By surrounding a block of code with `Venv`, a virtual environment can be created. This will hoist the code into the given namespace, allowing for at-runtime creation of module contexts. Using this, you could load an entire library just-in-time without clobbering the namespace of the client. Anything created in the virtual namespace will be transient, allowing you to test code without risk to the shared global Python namespace.

You probably don't need to use this. But if you have a really badly designed singleton class that clobbers its own global variables during execution, this can be a very fast way to quarantine and isolate it without introducing any side effects.

See the docstring for details on use. 

### wrapped

Subclassing and expanding on classes is usually pleasant in Python, but if that class is extremely clever (for example, using metaclasses) it may not be easy. Subclass `Wrapped` and then set the type to what you want to expand on, and `Wrapped` will use your code and for everything else interact as though it's that chosen type.

For example, the Sparkplug B specification uses Google Protobuf objects, and these can not be inherited sanely. Instead, you can do something like this:
```python
from .sparkplug_b_protobuf import Payload
from .wrapped import Wrapped

class SparkplugBPayload(Wrapped):

    _wrap_type = Payload
    _allow_identity_init = True
    
    def __init__(self, data=None):
        """Init for convenience. 
        If the data is already a protobuf payload, just use it.
        If the data is a string to be parsed, init normally and parse.
        """
        if isinstance(data, (str,unicode)):
            super(SparkplugBPayload, self).__init__()
            self._self.ParseFromString(data)
        else:
            super(SparkplugBPayload, self).__init__(data)
    
    def addMetric(self, name, alias, metric_type, value=None):
        """Helper method for adding metrics to a container which can be a
        payload or a template
        """
        metric = self.metrics.add()

        self.initMetric(metric, name, alias, metric_type, value)
        # Return the metric
        return metric
	
	# etc.
```
The `SparkplugBPayload` class here adds a helper function to the payload definition without interfering with the class itself. 

# Contributions

Please open an issue if there's any problems with the scripts. If you have corrections or additional features submit them or provide a pull request. Anything pulled in will be listed here. Thanks!

> Written with [StackEdit](https://stackedit.io/).
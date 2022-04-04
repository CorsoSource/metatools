# Metatools for Ignition
### _Tools to build tools with_
The following is an eclectic collection of functions, classes, and settings that make it easier to do specific tasks in Ignition. Each was built to assist a larger goal and are handy to have around, a means to an end. Many focus on introspection - allowing code to look at itself (and by extension _you_).

If you find an issues, bugs, failings, or disappointments - file an issue! Feature requests are appreciated, and pull requests triply so! Any modifications submitted will be called out and the script file will be updated with a `__credits__` listing with your name (plus, it'll be tracked by Github).

## Example Usage (pretty printing)

Of all the scripts, the pretty printing functions are probably the most handy. Here's an example of how to use it, as seen from the Ignition script console. In this we'll install the pretty printer to the prompt's `displayhook` which is a bit context sensitive.

```python
>>> some_dataset = shared.tools.examples.simpleDataset
>>> shared.tools.pretty.install()
>>> some_dataset
"some_dataset" <DataSet> of 3 elements and 3 columns
  ====================================================
          a                     |  b                     |  c                    
           <java.lang.Integer>  |   <java.lang.Integer>  |   <java.lang.Integer> 
  -------------------------------------------------------------------------------
   0 |                        1 |                      2 |                      3
   1 |                        4 |                      5 |                      6
   2 |                        7 |                      8 |                      9

>>> from shared.tools.pretty import p,pdir
>>> p
p(o, indent='  ', listLimit=42, ellipsisLimit=80, nestedListLimit=10, directPrint=True)

>>> pdir
pdir(o, indent='  ', ellipsisLimit=120, includeDocs=False, skipPrivate=True, recurseSkips=set([]), recursePrettily=False, directPrint=True)

>>> pdir(some_dataset)
  Properties of "some_dataset" <'com.inductiveautomation.ignition.common.BasicDataset'>
  =======================================================================================
  Dataset [3R ⅹ 3C]
  ---------------------------------------------------------------------------------------
  The most base type

  Attribute                 (P)   Repr                                                                                                                          <Type>                    
  --------------------      ---   ------------------------------------------------------------------------------------------------------------------------      -----------------------   
  asXML                           H4sIAAAAAAAAALOxr8jNUShLLSrOzM+zVTLUM1BSSM1Lzk/JzEu3VQoNcdO1ULK34+WySSm2s0nO                                                                            
                                 z7GzSbEztNFPAdEmUNocTOuDZaFKjKBSplDaAlOJMVTKDEpbIinRB9oGAKHjbYmaAAAA
  binarySearch                    λ(<int>, <java.lang.Object>)                                                                                                 instancemethod            
  bulkQualityCodes                None                                                                                                                          NoneType                  
  class                                                                                                                                                                                   
  columnContainsNulls             λ(<int>)                                                                                                                     instancemethod            
  columnCount                     3                                                                                                                             int                       
  columnNames                     [a, b, c]                                                                                                                     java.util.Collections     
  columnTypes                     [class java.lang.Integer, class java.lang.Integer, class java.lang.Integer]                                                   java.util.Collections     
  data                            array([Ljava.lang.Object;, [array(java.lang.Object, [1, 4, 7]), array(java.lang.Object, [2, 5, 8]), array(java.lang.O...      array.array               
  dataDirectly                    n/a                                                                                                                           write-only attr           
  datasetContainsNulls            λ()                                                                                                                          instancemethod            
  equals                          λ(<java.lang.Object>)                                                                                                        instancemethod            
  getAsXML                        λ()                                                                                                                          instancemethod            
  getBulkQualityCodes             λ()                                                                                                                          instancemethod            
  getClass                        λ()                                                                                                                          instancemethod            
  getColumnAsList                 λ(<int>)                                                                                                                     instancemethod            
  getColumnCount                  λ()                                                                                                                          instancemethod            
  getColumnIndex                  λ(<java.lang.String>)                                                                                                        instancemethod            
  getColumnName                   λ(<int>)                                                                                                                     instancemethod            
  getColumnNames                  λ()                                                                                                                          instancemethod            
  getColumnType                   λ(<int>)                                                                                                                     instancemethod            
  getColumnTypes                  λ()                                                                                                                          instancemethod            
  getData                         λ()                                                                                                                          instancemethod            
  getPrimitiveValueAt             λ(<int>, <int>)                                                                                                              instancemethod            
  getQualityAt                    λ(<int>, <int>)                                                                                                              instancemethod            
  getRowCount                     λ()                                                                                                                          instancemethod            
  getValueAt                      λ(<int>, <int>) -OR- (<int>, <java.lang.String>)                                                                             instancemethod            
  hashCode                        λ()                                                                                                                          instancemethod            
  notify                          λ()                                                                                                                          instancemethod            
  notifyAll                       λ()                                                                                                                          instancemethod            
  rowCount                        3                                                                                                                             int                       
  setAllDirectly                  λ(<java.util.List>, <java.util.List>, <[[Ljava.lang.Object;>)                                                                instancemethod            
  setColumnNames                  λ(<java.util.List>)                                                                                                          instancemethod            
  setColumnTypes                  λ(<java.util.List>)                                                                                                          instancemethod            
  setData                         λ(<[[Ljava.lang.Object;>)                                                                                                    instancemethod            
  setDataDirectly                 λ(<[[Ljava.lang.Object;>)                                                                                                    instancemethod            
  setFromXML                      λ(<java.util.List>, <java.util.List>, <java.lang.String>, <int>)                                                             instancemethod            
  setValueAt                      λ(<int>, <int>, <java.lang.Object>)                                                                                          instancemethod            
  toString                        λ()                                                                                                                          instancemethod            
  wait                            λ() -OR- (<long>) -OR- (<long>, <int>)                                                                                       instancemethod            

```

One of the neat tricks some of the functions ~~ab~~use is how aware of their surroundings they are. Note that the `p(some_dataset)` calls out the name of the _variable_ itself, and that `pdir(p)` lists out the arguments of the function. Note that `pdir(some_dataset)` not only lists all the attributes, but the signatures of functions and the values of attributes, _even though it is a Java object_.

## Testing

Tests are currently written for Python's built in `unittest` and `doctest` libraries. See the `test/shared/tools` folder for coverage.

#### Disclaimer
While **I** use the code here semi-regularly, do take a moment to understand any code you plan to use in production! This is always a good idea, but some of the scripts operate on Python magic. Some are extremely handy, like scope injection used in the `Logger` to make Python3-style string formatting. Others like `@async` gently abuse notation for convenience. And others like `Trap` violently abuse the Python's internal runtime machinery.

**NOTE**: The `shared.tools.debug.*` utilities are essentially a submodule of the metatools. It works, but is fairly large and has a huge test surface area, some of which is very hard to automate testing on. I've extensively tested the underlying mechanisms, but changes are not automatically subjected to unit tests; eventually, but it's a huge amount of work for what is, essentially, a personal tool. If you come up with a good test method, _please_ submit a pull request - you'll be clearly credited and it'll help make these tools ever more rigorous!

All the code is safe. All applications of it are _not_.  ...  Well, the debugger is theoretically wildly unsafe, but only in the sense of using a spanner on a running engine - be careful, roll your sleeves up, and be ready to restart. It has lots of safeguards, but it is operating on a live executing thread in situ.

That out of the way, here's the handy stuff! 

## Tracing Debugger

Jython has a version of the PDB (the Python Debugger). This is actually a three part machine, `pdb` is built on `bdb` (the base Python debugger class) and `cmd` (a generic command-line interpreter class). Unfortunately, a number of ideas did not get adjusted in the port: dealing with more than one instance of the debugger, multithreading / external inspection, it uses old-style Python classes, and `linecache` straight up does not work. The first point is actually reinforced by Jython's `PyTraceFunction` which has `synchronized(imp.class) { synchronized(this) {`, forcing all tracing to be one-at-a-time despite Jython's multithreaded nature.

All that is to say `shared.tools.debug.*` is a ground-up full reimplementation of these. Almost all of it is generic to Jython, but `CodeCache` specifically has mechanisms to deal with Ignition's many sources of code (though not all - many code sources are not yet resolvable, like Perspective components, SFCs, and WebDev resources).

In general, you only need to use the `Tracer` class in `shared.tools.debug.tracer`, and helper functions are included to replicate the old functionality of `import pdb; pdb.set_trace()` is now `shared.tools.debug.tracer.set_trace()`. Sorry it's slightly longer...

### Usage

The core of the engine is the `Tracer`. This class does all the heavy lifting. Basically, call the Tracer class on a thread: `Tracer(some_thread_object)` (if missing, it will initialize on the thread that executed it). A `tracer_id` can be provided, otherwise a short randomized string is generated; use this identifier to refer to the tracer in all contexts.

A tracer has a few distinct modes:
 * `monitoring` - the tracer is attached to `sys.settrace()` and is actively tracing, but is not directly interfering with execution flow. Dispatch continues until `.monitoring` is `False`.
 * `interdicting` - the tracer is actively preventing execution flow without direct external input. Commands are run until `.interdicting` is `False`.
 * `inactive` - the tracer is not reacting to its target thread. The tracer will do nothing until `.monitoring` is `True`.
 * `waiting` - another tracer is running or it is waiting for right-of-way to attach itself to `sys.settrace()`. The tracer can not leave this state until `sys.settrace(None)` clears and tracing mechanics become unblocked.

You may retrieve a tracer (running on the same JVM) via `Tracer[tracer_id]` or by index reference in `Tracer.tracers`.

Commands are strings and may be called by either `tracer.command('...')` or by using the shifting operator with the string `'continue' >> tracer`

In the event of something insane happening, or to stop tracing with extreme prejudice, use the `SCRAM()` call. It'll ram a tracer through its shutdown, and if called from the module `shared.tools.debug.tracer.SCRAM()` it'll crash and burn all tracked tracers. It puts the 'axe' in 'safety control rod axe man' - tracers slow things down and are very close to the metal, so I wanted a way to fix that if it went awry.

### A (very) short overview of how it operates

On initialization, the tracer configures itself. The key details are it hijacks the thread's `sys` object (literally the thread's specific `threadState` object's `systemState` property) allowing it to intercept and prevent the `Py` god class from muxing the threadstate on us (otherwise command run on the tracer would run on _the calling thread_ and utterly log jam the whole works). After the tracer notifies `ExtraGlobal` of its existence so it can be easily accessed by outside contexts. Once logged (and has right-of-way), it starts up the Python tracing machinery by setting `self.sys.settrace(NOP_TRACE)`; even though `sys` (aka the thread's `threadState.systemState`) is already thread-scoped, the machinery has monitor locks on the trace machinery forcing it to be one-at-a-time. The `NOP_TRACE` function does two things: checks the global `SCRAM_DEADMAN_SIGNAL` and checks if the current frame should be skipped; if the frame is something we _might_ care about, it returns itself `NOP_TRACE` to keep the trace active (a nice overview is at [How C Trace Functions Really Work](https://nedbatchelder.com/text/trace-function.html) - it's applicable to how Jython runs, an explains the "trampoline" mechanic well). The tracer is now primed and ready to _do things_.

Once monitoring is turned on, the tracer installs itself to the execution stack. First it assigns itself to all the stack frame's `f_trace` attribute to ensure its `self.dispatch` is called, even if the frame is past the initial `call` event (since the frame only calls for a trace function on frame entry). IMPORTANT: we never set `self.sys.settrace(self.dispatch)` from the outside - it _must_ be called from within the thread's context, otherwise we'll involve our thread in the trace mechanics and the whole thing just log jams _horribly_; by _only_ and _strictly_ setting the trace function from _within_ `self.dispatch` we're always in scope. This is part of the trick to getting everything to work: set all frame's `f_trace` manually to ensure dispatch is called, but do _**NOT**_ set the `settrace` until _we're already dispatching_. This is also why we _must_ turn on the trace machinery at the start to a no-op function: the trace mechanics must be **on** for the frame's `f_trace` to get called, but we **can not** set the class object to it until the master `Py` god class is executing the code from the correct `threadState`.

Once `self.dispatch` is self-sustaining and in control, the dispatch either skips the frame (if it's in the blacklist), dispatches user define dispatch events (`self.on_<EVENT>`), buffers the context (if on and `monitoring`), or awaits `pending_commands` to be non-empty (if `interdicting`). Traps and breakpoints are checked if `monitoring`, and if so will trip `interdicting` to `True`.

When the tracer shuts down, it sets its internal flags to false, clears its buffers, removes itself from `ExtraGlobal`, clears all frame's `f_trace` in the execution stack, and de-hijacks the thread's `sys` object. A `SCRAM` call will usually result in something graceless, but it does put a quick end to whatever the tracer is doing.

### Expansion

Subclassing `Tracer` is a simple way to bolt on more functionality. User override hooks are provided with `on_call`, `on_line`, `on_return`, and `on_exception`; these `on_*` functions are executed after failsafes and before the traps/breakpoints are checked. In most circumstances I think this is not needed, but it's nice if you have a specialized monitoring to perform without all the overhead of full interdiction.

The tracer could _theoretically_ be repurposed for other uses by adding additional `_dispatch_*` methods, where the `*` maps to an event that the tracer is called against. For Python tracing, the callback always calls with `frame, event, arg`, but overriding `dispatch` and changing the signature could adapt it.

All command functions start with `_command_`. All commands must have a doc string so the `help` command can explain what it does. Commands may have multiple names for convenience - simply assign the command to another Tracer attribute, like thise: `_command_h = _command_help`; when the Tracer class is initialized it resolves and maps all available commands.

Adding in new remote control functionality will likely intercept in `command_loop` or `_await_command`.

### Caveats

 * **Only one tracer can be actively running at a time** - again, the Jython tracing mechanics prevent more than one trace function from having any sort of interrupting wait loop at a time. Though the threads are separate, the trace mechanics utilize the underlying Java synchronization to prevent more than one at time; sleep will indeed continue to block, so no more than one tracing function can be run at a time, period. (A hack may be possible, but I do not know how to monkey patch Jython for it yet.)

 * **Immutable variables can not be changed** - Immutable object references can not point to new values, meaning that strings, ints, etc can not be changed. They can be assigned to, but it won't _stick_ since the object referenced by the frame's `f_locals` dict will have the same value; the new value is essentially only changed in the `exec` call's execution scope. Completely _new_ variables and _mutable_ variables get set and change just fine, though!
 
 * **The `jump` command can not be implemented** - Jython's frame object does not allow writing to `frame.f_lineno`. I do not know how to work around this yet, or even if it's fundamentally possible.


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

### expression

Safely convert a string into a function! Simply pass in a string and call it later:

```python
>>> from shared.tools.expression import Expression
>>> Expression('x + "asdf"')('qwer')
qwerasdf
>>> x = Expression('min(x)')
>>> x([2,1,3])
1
>>> Expression('c*(a-b)')(a=2, b=3, c=5)
-5
>>> Expression('c*(a-b)')._fields
<'tuple'> of 3 elements
   0   |    'a'
   1   |    'b'
   2   |    'c'

>>> Expression('c*(a-b)')(2,3,5)
-5
```

Note that this does _**not**_ use `eval` or `exec`. Instead it parses the string like it's Python, but manually compiles it into a function by parsing with Python's `tokenize`, converting to a postfix ordered opertion stack, and then resolving to actual objects/function calls.  The result is something kind of like Python's AST, but in a much simpler, dumber way. When the `Expression` is done initializing, the `Expression` object can be called directly, either with positional arguments or keyword arguments whose keys are values refrerenced in the given expression string. The end result is slower than code generated by Python's `compile`, but safer and faster than, say, just-in-time dict key lookups. It's a nice compromise, I think.

### global

Ever do work in one section of Ignition and wish you could exploit it in another? Tired of lag due to recalculating the same data over and over in different contexts? Use `ExtraGlobal` to cache objects for anything to reference in the JVM. It monitors itself and keeps track of its entries, purging (or updating) them as they time out. Handy if you have an event driven by a tag that you want to show in Perspective and reference in WebDev.

> WARNING: This is clearly best used for objects that are immutable, but there's nothing stopping you from using this as a weird, thread-unsafe pipe between threads. Don't use it for that. Unless you have a really good reason or are making something really cool.

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

> Note: consider placing this at the top of code modules so that the logger can be immediately switched on the gateway status page without waiting for a failure to trip it:
> ```python
> from shared.tools.logging import Logger; Logger().trace('Compiling module')
> ```

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

Additionally, the thread can be named with `name=`. Setting `maxAllowedRuntime=` will _make sure_ the thread dies in a certain amount of time. If you're worried an async thread will live past its prime, this is an easy way to make sure it's not there. Eventually. 

Also added is `findThreads` which will return a list of named threads matching a pattern given (i.e. regex). 

And for those cheating off other thread's work, you can use `getThreadObject` to get a live reference to something in another thread.
> WARNING: Grabbing and mutating objects _from outside threads_ is sheer lunacy and is beyond bad practice! This function exists to make `ExtraGlobal` functional and to overcome a few extremely niche edge cases in how Jython operates (as compared to, say, CPython).


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

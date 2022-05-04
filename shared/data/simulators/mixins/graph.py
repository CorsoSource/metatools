from transitions.extensions import GraphMachine


class GraphMixin(GraphMachine):

	def _init_graphviz_engine(self, use_pygraphviz):

		Graph = super(GraphMixin, self)._init_graphviz_engine(use_pygraphviz)

		class TweakedGraph(Graph):

			_TRANSITION_CHECK = self._TRANSITION_CHECK

			def _transition_label(self, tran):
				if tran.get('trigger') == self._TRANSITION_CHECK:
					return ''
				else:
					return super(TweakedGraph, self)._transition_label(tran)

		return TweakedGraph



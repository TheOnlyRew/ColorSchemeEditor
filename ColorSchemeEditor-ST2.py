import sublime, sublime_plugin, os.path

# globals suck, but don't know how to pass data between the classes
_schemeEditor = None
_skipNext = False
_wasSingleLayout = None
_lastScope = None
_lastScopeIndex = 0


def find_matches ( scope, founds ):
	global _schemeEditor

	ret = []
	maxscore = 0

	# find the scope in the xml that matches the most
	for found in founds:
		foundstr = _schemeEditor.substr( found )
		pos = foundstr.find( '<string>' ) + 8
		foundstr = foundstr[ pos : -9 ]
		foundstrs = foundstr.split( ',' )
		fstrlen = 0
		for fstr in foundstrs:
			fstrlen = len( fstr )
			fstr = fstr.lstrip( ' ' )
			padleft = fstrlen - len( fstr )
			fstr = fstr.rstrip( ' ' )
			score = sublime.score_selector( scope, fstr )
			if score > 0:
				a = found.a + pos + padleft
				ret.append( [ score, sublime.Region( a, a + len( fstr ) ) ] )
			pos += fstrlen + 1

	if len( ret ) == 0:
		return None
	else:
		return ret


def display_scope ( region ):
	global _schemeEditor

	sel = _schemeEditor.sel()
	sel.clear()
	sel.add( region )
	_schemeEditor.show_at_center( region )

	# Without window focus, the above `show_at_center` will not visibly modify
	# the current selection unless the new region is on a different line than
	# the old.
	# Momentarily give the _schemeEditor View focus to force the re-draw.
	# We have to capture the current View and Window to make sure the correct
	# View receives focus after the re-draw.
	current_window = sublime.active_window()
	current_view = current_window.active_view()
	scheme_window = _schemeEditor.window()

	scheme_window.focus_view(_schemeEditor)
	current_window.focus_view(current_view)


def update_view_status ( view ):
	global _lastScope, _lastScopeIndex

	found = None
	_lastScope = []
	_lastScopeIndex = 0

	# find the scope under the cursor
	scope_name = view.scope_name( view.sel()[0].a )
	pretty_scope = scope_name.strip( ' ' ).replace( ' ', ' > ' )
	scopes = reversed( pretty_scope.split( ' > ' ) )

	# convert to regex and look for the scope in the scheme editor
	for scope in scopes:
		if len( scope ) == 0:
			continue
		dots = scope.count( '.' )
		regex = r'<key>scope</key>\s*<string>([a-z\.\-\+]* ?, ?)*([a-z\.\-\+ ]*'
		regex += scope.replace( '.', r'(\.' )
		while dots > 0:
			regex += ')?'
			dots -= 1
		regex += r')( ?, ?[a-z\.\-\+]*)*</string>'

		found = _schemeEditor.find_all( regex, 0 )
		found = find_matches( scope, found )
		if found != None:
			_lastScope += found

	scopes = len( _lastScope )
	sublime.status_message( 'matches ' + str( scopes ) + ': ' + pretty_scope )
	if scopes == 0:
		_lastScope = None
		display_scope( sublime.Region( 0, 0 ) )
	else:
		_lastScope.sort( key = lambda f: f[1].a )
		_lastScope.sort( key = lambda f: f[0], reverse = True )
		display_scope( _lastScope[0][1] )


def kill_scheme_editor ():
	global _schemeEditor, _skipNext, _wasSingleLayout, _lastScope, _lastScopeIndex
	if int( sublime.version() ) > 3000 and _wasSingleLayout != None:
		_wasSingleLayout.set_layout( {
			'cols': [0.0, 1.0],
			'rows': [0.0, 1.0],
			'cells': [[0, 0, 1, 1]]
		} )
	_skipNext = False
	_wasSingleLayout = None
	_schemeEditor = None
	_lastScope = None
	_lastScopeIndex = 0



# listeners to update our scheme editor
class NavigationListener ( sublime_plugin.EventListener ):

	def on_close ( self, view ):
		global _schemeEditor

		if _schemeEditor != None:
			if _schemeEditor.id() == view.id():
				kill_scheme_editor()

	def on_selection_modified ( self, view ):
		global _schemeEditor, _skipNext

		if _schemeEditor != None:
			if _schemeEditor.id() != view.id() and not view.settings().get( 'is_widget' ):
				if _skipNext:
					_skipNext = False
				else:
					update_view_status( view )


	def on_text_command( self, view, command_name, args ):
		global _schemeEditor, _skipNext

		if _schemeEditor != None:
			if command_name == "drag_select":
				# The 'drag_select' text command only fires once (on mouse-down)
				# but `on_selection_modified` fires twice (on mouse-down and
				# mouse-up). Use the 'drag_select' command to trigger a skip.
				_skipNext = True
			elif command_name == "show_scope_name":
				# 'show_scope_name' triggers `on_selection_modified` for some
				# reason. Skip the next `on_selection_modified` when we see a
				# 'show_scope_name'.
				_skipNext = True



class EditColorSchemeNextScopeCommand ( sublime_plugin.TextCommand ):

	def run ( self, edit ):
		global _schemeEditor, _lastScope, _lastScopeIndex, _skipNext

		if _schemeEditor != None and _lastScope != None:
			scopes = len( _lastScope )
			if scopes > 1:
				_lastScopeIndex += 1
				if _lastScopeIndex == scopes:
					_lastScopeIndex = 0
				display_scope( _lastScope[_lastScopeIndex][1] )
				# Giving the _schemeEditor focus (as part of `display_scope`)
				# will trigger an `on_selection_modified`. Skip that one.
				_skipNext = True
			sublime.status_message( 'Scope ' + str( _lastScopeIndex + 1 ) + ' of ' + str( scopes ) )



class EditColorSchemePrevScopeCommand ( sublime_plugin.TextCommand ):

	def run ( self, edit ):
		global _schemeEditor, _lastScope, _lastScopeIndex, _skipNext

		if _schemeEditor != None and _lastScope != None:
			scopes = len( _lastScope )
			if scopes > 1:
				if _lastScopeIndex == 0:
					_lastScopeIndex = scopes - 1
				else:
					_lastScopeIndex -= 1
				display_scope( _lastScope[_lastScopeIndex][1] )
				# Giving the _schemeEditor focus (as part of `display_scope`)
				# will trigger an `on_selection_modified`. Skip that one.
				_skipNext = True
			sublime.status_message( 'Scope ' + str( _lastScopeIndex + 1 ) + ' of ' + str( scopes ) )



class EditCurrentColorSchemeCommand ( sublime_plugin.TextCommand ):

	def run ( self, edit ):
		global _schemeEditor, _wasSingleLayout

		view = self.view
		viewid = view.id()
		window = view.window()
		if _schemeEditor == None:

			# see if not trying to edit on the scheme file
			path = os.path.abspath( sublime.packages_path() + '/../' + view.settings().get( 'color_scheme' ) )
			if path == view.file_name():
				sublime.status_message( 'Select different file from the scheme you want to edit' )
				_schemeEditor = None
				return

			# see if we openeded a new view
			views = len( window.views() )
			_schemeEditor = window.open_file( path )
			if _schemeEditor == None:
				sublime.status_message( 'Could not open the scheme file' )
				return
			if views == len( window.views() ):
				views = 0
			else:
				views = 1

			# if we have only one splitter, open new one
			groups = window.num_groups()
			group = -1
			index = 0
			if groups == 1:
				_wasSingleLayout = window
				group = 1
				window.set_layout( {
					'cols': [0.0, 0.5, 1.0],
					'rows': [0.0, 1.0],
					'cells': [[0, 0, 1, 1], [1, 0, 2, 1]]
				} )
			elif views == 1:
				activegrp = window.active_group() + 1
				if activegrp == groups:
					group = activegrp - 2
					index = len( window.views_in_group( group ) )
				else:
					group = activegrp

			if groups == 1 or views == 1:
				# move the editor to another splitter
				window.set_view_index( _schemeEditor, group, index )
			else:
				#if the editor is in different splitter already focus it
				window.focus_view( _schemeEditor )

			window.focus_view( view )
			update_view_status( view )

		else:
			# if it was us who created the other splitter close it
			if _wasSingleLayout != None:
				_wasSingleLayout.set_layout( {
					'cols': [0.0, 1.0],
					'rows': [0.0, 1.0],
					'cells': [[0, 0, 1, 1]]
				} )
			kill_scheme_editor()

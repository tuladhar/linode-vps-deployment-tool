#!/usr/bin/env python
# *-* coding: utf-8 *-*

try:
	import sys
	import ConfigParser
	import libcloud
	import libcloud.security
	import libcloud.compute.types
	import libcloud.compute.providers
	import libcloud.compute.deployment
	import libcloud.compute.drivers.linode
	import os
	import time
	import traceback
	import collections
	import string
	import random
except ImportError, imperr:
	print >> sys.stderr, "fatal: %s" % str(imperr)
	sys.exit(1)

__program__=sys.argv[0]

def log(level, message):
	try:
		_message = str(message)
		if level == "info":
			print >> sys.stdout, "info: %s" % _message
		elif level == "debug" and Linode.debug == True:
			print >> sys.stderr, "debug: %s" % _message
		elif level == "fatal":
			print >> sys.stderr, "fatal: %s" % _message
			sys.exit(1)
	except Exception as err:
		log("fatal", extract_tb())

def break_point():
	print >> sys.stderr, ">> break point <<"
	sys.exit(1)

def extract_tb():
	exc_message = str()
	exc_type, exc_value, exc_traceback = sys.exc_info()
	for (f, l, m, r) in traceback.extract_tb(exc_traceback):
		exc_message = "Exception (%s)\nTraceback Info:\n> file: %s\n> line: %d\n> method: %s\n> statement: %s\n> reason: %s" % (exc_type, f, l, m, r, exc_value)
		break	# recent traceback only
	return exc_message

def print_usage():
	_usage_="""\
Usage: python %s command [section]

Available commands:

  listnodes       List all the available nodes in your account
  listplans       List all the available Linode VPS plans (i.e size)
  listimages      List all the available Linode OS image templates
  listlocations   List all the available Linode VPS Physical Location
  deploy          Deploy a node given its section name as defined in `%s'
  configtest      Test the configuration file
  help            Display this help message and exit
""" % (__program__, Linode.SETTINGS_FILENAME)
	print >> sys.stderr, _usage_
	sys.exit(1)

def parse_args():
	if len(sys.argv) == 1:
		print 'Usage: python %s command [section]' % __program__
		print "Try `help' command."
		sys.exit(1)

 	if len(sys.argv) >= 2 and sys.argv[1] in ['help','-h','--help']: print_usage()
	
	Linode.command=sys.argv[1]
	if Linode.command not in Linode.LIST_OF_COMMANDS:
		log("fatal", "Unknown command '%s'." % Linode.command)

	if len(sys.argv) == 2:
		if Linode.command == "listplans":
			log("info", "Listing all the available Linode VPS plans...")
			Linode.listplans()
			tblfmt = " %-2s %-15s %-6s"
			title = tblfmt % ("ID", "PLAN NAME", "PRICE")
			sep = '-' * len(title)
			print >> sys.stdout, sep
			print >> sys.stdout, title
			print >> sys.stdout, sep
			for plan in Linode.plans:
				print >> sys.stdout, tblfmt % (plan.id, plan.name, plan.price)
		elif Linode.command == "listimages":
			log("info", "Listing all the available Linode OS images...")
			Linode.listimages()
			tblfmt = " %-4s %-30s "
			title = tblfmt % ("ID", "NAME")
			sep = '-' * len(title)
			print >> sys.stdout, sep
			print >> sys.stdout, title
			print >> sys.stdout, sep
			for image in Linode.images:
				print >> sys.stdout, tblfmt % (image.id, image.name)
			return None
		elif Linode.command == "listlocations":
			log("info", "Listing all the available Linode VPS physical locations...")
			Linode.listlocations()
			tblfmt = " %-3s %-20s %-8s "
			title = tblfmt % ("ID", "LOCATION", "COUNTRY")
			sep = '-' * len(title)
			print >> sys.stdout, sep
			print >> sys.stdout, title
			print >> sys.stdout, sep
			for location in Linode.locations:
				print >> sys.stdout, tblfmt % (location.id, location.name, location.country)
			return None
		elif Linode.command == "listnodes":
			log("info", "Listing all the nodes belonging to your account....")
			Linode.listnodes()
			tblfmt = " %-10s %-20s %-5s %-10s %-40s %-20s %-20s "
			title = tblfmt % ("Linode ID", "Name", "Size", "State", "UUID", "Public IP", "Private IP")
			title_sep = '-' * len(title)
			print >> sys.stdout, title_sep
			print >> sys.stdout, title
			print >> sys.stdout, title_sep
			for node in Linode.nodes:
				if node.state == 0: state = "RUNNING"
				elif node.state == 2: state = "BOOTING"
				elif node.state == 3: state = "BRAND NEW"
				else: state = node.state
				print >> sys.stdout, tblfmt % (node.id, node.name, node.size, state, node.uuid, node.public_ip, node.private_ip)
		elif Linode.command == "configtest":
			Linode.configtest()
		elif Linode.command == "deploy":
			log("fatal", "Invalid command 'deploy': Node section name required.")
		else:
			log("fatal", "No such command '%s'." % Linode.command)
	elif len(sys.argv) == 3 and Linode.command == 'deploy':
		Linode.deploy_section = sys.argv[2]
		if Linode.deploy_section not in Linode.cfg.sections():
			log("fatal", "Invalid command `deploy': No such node section named `%s'." % Linode.deploy_section)
		else:
			Linode.deploy_init()
			Linode.deploy_finalize()
			Linode.start_deploy()
	elif len(sys.argv) >= 3:
		log("fatal", "Invalid command `%s': Excess arguments." % Linode.command)
	
class BootstrapTemplate(string.Template):
	delimiter='%'
	def __init__(self, s):
		super(BootstrapTemplate, self).__init__(s)

class Linode:
	LIST_OF_COMMANDS=["listplans", "listimages", "listlocations", "listnodes", "configtest", "deploy", "help"]
	REQUIRE_NODE_SECTION_OPTS=[("hostname", "string"), ("plan_id", "int"), ("image_id", "int"), ("location_id", "int"), ("script_deployment", "string"), ("ssh_key_deployment", "string")]
	SETTINGS_FILENAME="linode.settings"
	debug=False
	api_key=str()					# Linode API
	cfg=None							# ConfigParse instance
	command=str()
	node_sections=list()	# List of node sections in the settings
	deploy_section=str()	# Name of the section being deployed
	deploy_section_options=collections.OrderedDict()
	connection=None				# Linode Driver instance
	nodes=images=plans=locations=None		# Linode Compute instances
	hostname=image=plan=location=None		# Linode Compute instance
	script_deployment_filename=ssh_deployment_filename=ssh_deployment_content=script_deployment_content=str()
	deployed_node=None		# Linode Deployed node instance
	
	def __init__(self): pass
  
	@staticmethod
	def cfg_init():
		Linode.cfg = ConfigParser.ConfigParser()
		try:
			# READ CONFIGURATION FILE
			if Linode.cfg.read(Linode.SETTINGS_FILENAME) == []:
				log("fatal", "Unable to open configuration file: No such file `%s' in the current directory." % (Linode.SETTINGS_FILENAME))
			# VALIDATE MAIN SECTION
			Linode.validate_main_section()
			# ENABLE/DISABLE DEBUG
			if Linode.cfg.has_option("main", "debug") and Linode.cfg.getboolean("main", "debug") == True:
				Linode.debug=True
			if Linode.cfg.has_option("main", "api_debug") and Linode.cfg.getboolean("main", "api_debug") == True:
				libcloud.enable_debug(sys.stdout)
		except ConfigParser.Error as parsererr:
			log("fatal", "Unable to parse configuration file: %s" % parsererr)
		except Exception:
			log("fatal", extract_tb())
		else:
			log("debug", "Configuration initialized.")

	@staticmethod
	def driver_init():
		log("debug", "calling driver_init()")
		log("debug", "Initializing Linode driver...")
		try:
			log("debug", "Disabling VERIFY_SSL_CERT...")
			libcloud.security.VERIFY_SSL_CERT=False
			#libcloud.security.VERIFY_SSL_CERT_STRICT=False
			
			Driver=libcloud.compute.providers.get_driver(libcloud.compute.types.Provider.LINODE)
			Linode.connection=Driver(Linode.api_key)
			if type(Linode.connection) != libcloud.compute.drivers.linode.LinodeNodeDriver:
				log("fatal", "Unable to initialized Linode driver.")
		except Exception:
			log("fatal", extract_tb())
		else:
			log("debug", "Linode driver initialized.")

	@staticmethod
	def deploy_init():
		log("debug", "calling deploy_init()")
		log("info", "Initializing node deployment `%s'..." % Linode.deploy_section)
		
		if not Linode.deploy_section in Linode.cfg.sections():
			log("info", "Nothing to do. No such section `%s' in the configuration file." % Linode.deploy_section)
			sys.exit(0)
		else:
			Linode.validate_node_section(Linode.deploy_section)
		
		options = Linode.cfg.options(Linode.deploy_section)		# Get all the options [hostname, plan_id, ...] of the deploy section
		for option in options:
			for _option, _option_type in Linode.REQUIRE_NODE_SECTION_OPTS:
				try:
					if option == _option:
						v = None
						if _option_type == "string":
							v = Linode.cfg.get(Linode.deploy_section, option).replace('"', '').replace("'", '')
						elif _option_type == "int":
							v = Linode.cfg.getint(Linode.deploy_section, option)
						elif _option_type == "boolean":
							v = Linode.cfg.getboolean(Linode.deploy_section, option)
						Linode.deploy_section_options[option]=v
						break		# exit from inner for loop and go to outer for loop
					else:
						continue		# continue the inner for loop until we get the option value
				except Exception:
					log("fatal", extract_tb())
		log("debug", "Node deployment initialized.")

	@staticmethod
	def deploy_finalize():
		log("debug", "calling deploy_finalize()")
		log("debug", "Finalizing node deployment `%s'..." % Linode.deploy_section)
		log("info", "Checking `%s' deployment settings..." % Linode.deploy_section)

		for option, value in Linode.deploy_section_options.items():		# OrderedDict
			log("debug", "Verifying `%s'..." % option)
			fmt="%s = %s ---> %s"
			if option == 'hostname':
					Linode.hostname = value
			elif option == 'plan_id':
				Linode.listplans()
				found=False
				for plan in Linode.plans:
					if int(plan.id) == value:
						Linode.deploy_plan=plan		# Store the plan instance
						log("info", fmt % (option, value, plan.name))
						found=True
						break
				if found: continue
				else: log("fatal", "Invalid node section [%s]: plan_id `%d' does not exists. Try `python %s listplans'." % (Linode.deploy_section, value, __program__))
			elif option == 'image_id':
				Linode.listimages()
				found=False
				for image in Linode.images:
					if int(image.id) == value:
						Linode.deploy_image=image
						log("info", fmt % (option, value, image.name))
						found=True
						break
				if found: continue
				log("fatal", "Invalid node section [%s]: image_id `%d' does not exists. Try `python %s listimages'." % (Linode.deploy_section, value, __program__))
			elif option == 'location_id':
				Linode.listlocations()
				found=False
				for location in Linode.locations:
					if int(location.id) == value:
						Linode.deploy_location = location
						log("info", fmt % (option, value, location.name))
						found=True
						break
				if found: continue
				log("fatal", "Invalid node section [%s]: location_id `%d' does not exists. Try `python %s listlocations'." % (Linode.deploy_section, value, __program__))
			elif option == "script_deployment":
				filename=Linode.script_deployment_filename=os.path.expanduser(value)
				if os.path.isfile(filename): 
					try:
						log("debug", "Reading deployment script `%s'..." % value)
						with open(filename) as fo:
							for line in fo.readlines():
								Linode.script_deployment_content += line
						log("info", fmt % (option, value, "OK"))
						continue		# outer for loop
					except Exception:
						log("fatal", extract_tb())
				else:
					log("fatal", "script_deployment: No such file '%s'." % value)
			elif option == "ssh_key_deployment":
				filename=Linode.ssh_deployment_filename=os.path.expanduser(value)
				if os.path.isfile(filename) == True:
					try:
						log("debug", "Reading deployment SSH key (%s)..." % value)
						with open(filename) as fo:
							Linode.ssh_deployment_content = fo.read()
						log("info", fmt % (option, value, "OK"))
						continue	 # outer for loop
					except Exception:
						log("fatal", extract_tb())
				else:
					log("fatal", "ssh_key_deployment: No such file '%s'." % value)
		log("debug", "Deployment settings OK.")
				
		# Prompt for re-checking
		while True:
			ans = raw_input("Is this correct [y/n]? ")
			if ans.lower() in ['yes', 'y']: break
			if ans.lower() in ['n', 'no']: log("fatal", "Exiting..."); sys.exit(1);
		log("debug", "Node deployment finalized `%s'." % Linode.deploy_section)

	@staticmethod
	def start_deploy():
		log("debug", "calling start_deploy()")
		log("info", "Starting node deployment...")
		try:
			log("debug", "Setting up deployment options...")
			plan=Linode.deploy_plan
			image=Linode.deploy_image
			location=Linode.deploy_location

			# Create temporary file for storing bootstrap script data with variable interpolated.
			log("debug", "Creating temporary file...")
			tempfilename="%s.%s" % (Linode.script_deployment_filename, random.randint(0, 9999999))

			# Create custom template and interpolate variables.
			template = BootstrapTemplate(Linode.script_deployment_content)
			template_variables = {
				"hostname": Linode.hostname
			}
			content = template.safe_substitute(template_variables)
			# Read content data and write to temporary file.
			with open(tempfilename, 'w') as fo:
				for line in content.splitlines():
					fo.write(line+'\n')
			log("debug", "Applying executable mode on temporary file...")
			os.chmod(tempfilename, 0755)
			log("debug", "Temporary file created `%s'." % tempfilename)
			break_point()
			
			log("debug", "Initializing SSHKeyDeployment...")
			ssh_key_deploy = libcloud.compute.deployment.SSHKeyDeployment(open(Linode.ssh_deployment_filename).read())

			log("debug", "Initializing ScriptFileDeployment...")
			script_file_deploy = libcloud.compute.deployment.ScriptFileDeployment(tempfilename)
		
			log("debug", "Initializing MultiSetupDeployment...")
			multi_step_deploy = libcloud.compute.deployment.MultiStepDeployment([ssh_key_deploy, script_file_deploy])
			
			log("debug", "Starting deployment timer..."); timer_start=time.time()
			
			log("info", "Deploying node `%s'... This may take a while. DO NOT INTERRUPT." % Linode.deploy_section)
			log("debug", "Invoking deploy_node() api call...")
			Linode.deployed_node = Linode.connection.deploy_node(name=Linode.deploy_section, image=image, size=plan, location=location, deploy=multi_step_deploy)

			log("debug", "Removing temporary file `%s'..." % tempfilename)
			try: os.remove(tempfilename)
			except: pass

			log("debug", "Stopping deployment timer..."); timer_end=time.time()
			timer_delta = timer_end - timer_start

			log("info", "Node successfully deployed in %.2f seconds." % timer_delta)
			log("info", "Run `listnodes' command to verify the newly deployed node.")
			
		except Exception:
			log("fatal", extract_tb())

	@staticmethod
	def listplans():
		log("debug", "Invoking list_sizes() api call...")
		try: Linode.plans=Linode.connection.list_sizes()
		except Exception: log("fatal", extract_tb())

	@staticmethod
	def listimages():
		log("debug", "Invoking list_images() api call...")
		try: Linode.images=Linode.connection.list_images()
		except Exception: log("fatal", extract_tb())

	@staticmethod
	def listlocations():
		log("debug", "Invoking list_locations() api call...")
		try: Linode.locations=Linode.connection.list_locations()
		except Exception:log("fatal", extract_tb())

	@staticmethod
	def listnodes():
		log("debug", "Invoking list_nodes() api call...")
		try: Linode.nodes = Linode.connection.list_nodes()
		except Exception: log("fatal", extract_tb())

	@staticmethod
	def configtest(): 
		log("debug", "Validating configuration file `%s'..." % Linode.SETTINGS_FILENAME)
		try:
			Linode.node_sections=Linode.cfg.sections()
			Linode.node_sections.remove('main')	# remove main section
			for node_section in Linode.node_sections:
				Linode.validate_node_section(node_section)
		except Exception, err:
			log("fatal", extract_tb())
		else:
			log("info", "OK.")
	
	@staticmethod
	def validate_main_section():
		log("debug", "Validating section `main'...")
		if Linode.cfg.has_section("main") == False:
			log("fatal", "Invalid configuration file (%s), section 'main' missing." % Linode.SETTINGS_FILENAME)
		elif Linode.cfg.has_option("main", "api_key") == False or Linode.cfg.get("main", "api_key") == '':
			log("fatal", "Invalid configuration file (%s), option 'api_key' missing or empty in 'main' section." % Linode.SETTINGS_FILENAME)
		else: Linode.api_key=Linode.cfg.get("main", "api_key").replace('"', '')
		log("debug", "Section OK.")
	
	@staticmethod
	def validate_node_section(section):
		log("debug", "Validating section `%s'..." % section)
		try:
			node_section_opts=Linode.cfg.options(section)
			for require_opt, require_opt_type in Linode.REQUIRE_NODE_SECTION_OPTS:
				if not require_opt in node_section_opts:
					log("fatal", "Invalid node section [%s]: option `%s' missing." % (section, require_opt))
				try:
					if require_opt_type == "string":
						if Linode.cfg.get(section, require_opt) == '':
							log("fatal", "Invalid node section [%s]: option `%s' empty." % (section, require_opt))
					elif require_opt_type == "int": Linode.cfg.getint(section, require_opt)
					elif require_opt_type == "boolean": Linode.cfg.getboolean(section, require_opt)
				except ValueError:
					log("fatal", "Invalid node section [%s]: option `%s' required value of type '%s'." % (section, require_opt, require_opt_type))

				except Exception:
					log("fatal", extract_tb())
		except Exception:
			log("fatal", extract_tb())
		else:
			log("debug", "Section OK.")
			return True

if __name__ == "__main__":
	Linode.cfg_init()
	Linode.driver_init()
	parse_args()

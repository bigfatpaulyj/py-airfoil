#!/usr/bin/python2.6

##//
##//    Copyright 2011 Paul White
##//
##//    This file is part of py-airfoil.
##//
##//    This is free software: you can redistribute it and/or modify
##//    it under the terms of the GNU General Public License as published by
##//    the Free Software Foundation, either version 3 of the License, or
##//    (at your option) any later version.
##
##//    This is distributed in the hope that it will be useful,
##//    but WITHOUT ANY WARRANTY; without even the implied warranty of
##//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##//    GNU General Public License for more details.
##//
##//    You should have received a copy of the GNU General Public License
##//    along with FtpServerMobile.  If not, see <http://www.gnu.org/licenses/>.
##//
from airfoil import Airfoil, Obj
import array
from control import *
import cProfile
from euclid import *
import itertools
import manage
from math import sqrt, atan2
import mesh
import optparse
import os
#import view
from proxy import *
import pyglet
from pyglet.gl import *
from pyglet import window, font, clock # for pyglet 1.0
from pyglet.window import key
import random
from skybox import *
from sound import *
import sys
from threading import Condition
from time import sleep
import traceback
from util import X_UNIT, Y_UNIT, Z_UNIT
from view import EXTERNAL, INTERNAL, View

def loadTerrain():
	global cterrain
	colFileName = ''
	mapFileName = ''
	if os.name == 'nt':
		cterrain = cdll.LoadLibrary("bin\cterrain.dll")
		colFileName = "data\\strip1.bmp"
		mapFileName = "data\\map_output.hm2"
	else:
		cterrain = cdll.LoadLibrary("bin/cterrain.so")
		colFileName = "data/strip1.bmp" 
		mapFileName = "data/map_output.hm2"

	cterrain.init(c_char_p(colFileName), 
		      c_char_p(mapFileName), 
		      c_float(4.0/3.0*2.0),
		      c_int(0),
		      c_float(10.0),
		      c_float(0.2))

def drawTerrain(view):
	pointOfView = (c_float * 6)()
	cameraVectors = view.getCamera().getCameraVectors()
        cameraCenter = cameraVectors[0]
        cameraPosition = cameraVectors[1]
	pointOfView[0] = cameraPosition[0]
	pointOfView[1] = cameraPosition[1]
	pointOfView[2] = cameraPosition[2]
	pointOfView[3] = cameraCenter[0]
	pointOfView[4] = cameraCenter[1]
	pointOfView[5] = cameraCenter[2]
	cterrain.draw(pointOfView)

BULLET_MASS=1.0
BULLET_DRAG_COEFF=0.05/BULLET_MASS
class Bullet(Obj, ControlledSer):
    TYP=3
    #LIFE_SPAN is in seconds
    LIFE_SPAN=30
    OFFSET=Vector3(0, -15, 0)
    VEL=Vector3(0, -750, 0)
    __IN_FLIGHT=set()

    @classmethod
    def getInFlight(cls):
        return cls.__IN_FLIGHT

    def __init__(self, ident=None, pos = Vector3(0,0,0), attitude = Quaternion(0.5,-0.5,0.5, 0.5), vel = Vector3(0,0,0), proxy=None, parent=None):
        Obj.__init__(self, pos=pos, attitude=attitude, vel=vel)
        self._mass = BULLET_MASS
	
        self._scales = [0.032, 0.032, 0.005]
	self.__parent=parent
        ControlledSer.__init__(self, Bullet.TYP, ident, proxy=proxy)

    def remoteInit(self, ident):
	    ControlledSer.remoteInit(self, ident)
	    self.__played=False

    def localInit(self):
        ControlledSer.localInit(self)
	(self._just_born, self._just_dead)=(True, False)
	self.__start=manage.now
	if self not in Bullet.__IN_FLIGHT:
		Bullet.__IN_FLIGHT.add(self)
		if(len(self.__class__.__IN_FLIGHT)%25==0):
			print 'num bullets (more): '+str(len(self.__class__.__IN_FLIGHT))

    def deserialise(self, ser, estimated):
	    obj=ControlledSer.deserialise(self, ser, estimated)
	    return obj
    
    def serNonDroppable(self):
	    self._flags &= ~self.DROPPABLE_FLAG
	    return [ self.__parent ]

    def deserNonDroppable(self, parent):
	    self.__parent=parent
	    return self

    def play(self):
	    if not self.__played and self.__parent is not None and self.__parent in manage.proxy and not self.local():
		    self.__played=True
		    manage.proxy.getObj(self.__parent).gunSlot.play(pos=self.getPos())

    def markDead(self):
	    ControlledSer.markDead(self)
            if self in Bullet.__IN_FLIGHT:
       		    self._just_dead=True	
                    Bullet.__IN_FLIGHT.remove(self)

    def isClose(self, obj):
        return obj.getId()==self.getId()

    def _updateVelFromEnv(self, timeDiff):
        self._updateVelFromGrav(timeDiff)
        #Drag, acts || to Velocity vector
        #dv  = self.getDragForce(timeDiff) * timeDiff / self._mass
	self._velocity-=self._velocity*BULLET_DRAG_COEFF*timeDiff
	
    def _updateFromEnv(self, timeDiff):
        self._updateVelFromEnv(timeDiff)

    def getDragForce(self, drag=0.0): 
	    return self._velocity * 0.05

    def update(self):
        if self.getId() in self._proxy:
            rs=self._proxy.getObj(self.getId()) #rs = remote_self
            (self._pos, self._attitude, self._velocity)=(rs._pos, rs._attitude, rs._velocity)

	if manage.now-self.__start > Bullet.LIFE_SPAN or self.getPos().y<=0:
            self.markDead()
            self.markChanged()

    def estUpdate(self):
        timeDiff=self._getTimeDiff()
	self._updateVelFromEnv(timeDiff)
        self._updatePos(timeDiff)
  
    def serialise(self):
        (self._just_born, self._just_dead) = (False, False)
	return ControlledSer.serialise(self)

    def justBornOrDead(self):
        return self._just_born or self._just_dead

    @classmethod
    def drawAll(cls):
	    #glPushMatrix()
	    glDisable(GL_CULL_FACE)
            #glTranslatef(self._pos.x, self._pos.y, self_pos.z)
            glBegin(GL_POINTS)
            glColor4f(1.0,1.0,1.0,1.0)
	    for p in cls.positions:
		    glVertex3f(p.x, p.y, p.z)
            glEnd()
	    #glPopMatrix()
	    cls.positions=[]

    def draw(self):
        try:
            assert self.alive()
	    Bullet.positions.append(self._pos)
        except AssertionError:
            print_exc()
Bullet.positions=[]

class MyAirfoil(Airfoil, ControlledSer):
    UPDATE_SIZE=Mirrorable.META+12
    [ _POS,_,_, _ATT,_,_,_, _VEL,_,_, _THRUST ] = range(Mirrorable.META+1, UPDATE_SIZE)
    TYP=0

    def __init__(self, controls=None, proxy=None, 
                 pos = Vector3(0,0,0), 
                 attitude = Quaternion(0.5, -0.5, 0.5, 0.5), 
                 velocity = Vector3(0,0,0), 
                 thrust = 0, ident=None):
	global cterrain
	Airfoil.__init__(self, pos, attitude, velocity, thrust, cterrain)
	ControlledSer.__init__(self, MyAirfoil.TYP, ident, proxy)
	self.setControls(controls)

    def setControls(self, c):
	self.__controls=c

    def localInit(self):
        ControlledSer.localInit(self)
        self.__interesting_events = [Controller.THRUST, Controller.PITCH, Controller.ROLL, Controller.FIRE]
        self.__thrustAdjust = 400
        self.__pitchAdjust = 0.01
        self.__rollAdjust = 0.01
        self.__bullets=[]
        self.__last_fire=manage.now
	self.frame_rot=None

    def remoteInit(self, ident):
	    ControlledSer.remoteInit(self, ident)
	    self.__lastKnownPos=Vector3(0,0,0)
	    self.__lastDelta=Vector3(0,0,0)
	    self.__lastUpdateTime=0.0
	    self.__played=False
	    self.__play_tire=False

    def estUpdate(self):
        period=manage.now-self.__lastUpdateTime
        self.setPos(self.__lastKnownPos+
                    (self.__lastDelta*period))
        return self

    def eventCheck(self):
        if not Controls:
            raise NotImplementedError
        events = self.__controls.eventCheck(self.__interesting_events)

        self.changeThrust(events[Controller.THRUST]*self.__thrustAdjust)
        if events[Controller.PITCH]!=0:
            self.adjustPitch(events[Controller.PITCH]*self.__pitchAdjust)
        if events[Controller.ROLL]!=0:
            self.adjustRoll(-events[Controller.ROLL]*self.__rollAdjust)
	if events[Controller.FIRE]!=0 and manage.now-self.__last_fire>Airfoil._FIRING_PERIOD:
		frame_rot=self._attitude*mesh.SETUP_ROT
		vOff=self.getVelocity().normalized()+frame_rot* Bullet.VEL
		
		b=Bullet(pos=self.getPos()+frame_rot*Bullet.OFFSET, attitude=self._attitude.copy(), vel=self.getVelocity()+vOff, proxy=self._proxy, parent=self.getId())
		b.update()
		b.markChanged(full_ser=True)
		self.__last_fire=manage.now
		#mesh.deleteVBOs()
		#mesh.createVBOs(mesh.vbo_meshes)
		#glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        self.__controls.clearEvents(self.__interesting_events)

    def play(self):
	    if not self.local() and not self.__played:
		    self.__played=True
		    self.__engineNoise=SoundSlot("airfoil engine "+str(self.getId()), loop=True)
		    self.gunSlot=SoundSlot("gun "+str(self.getId()), snd=GUN_SND)
		    self.tireSlot=SoundSlot("tire screech"+str(self.getId()), snd=SCREECH_SND)

	    if self.__engineNoise.playing:
		    if self.thrust<=0:
			    if self.__engineNoise.snd is ENGINE_SND:
				    self.__engineNoise.play(snd=WIND_SND)
		    else:
			    if self.__engineNoise.snd is WIND_SND:
				    self.__engineNoise.play(snd=ENGINE_SND)
	    else:
		    if self.thrust>0:
			    self.__engineNoise.play(snd=ENGINE_SND)
		    else:
			    self.__engineNoise.play(snd=WIND_SND)
	    self.__engineNoise.setPos(self._pos)
	    spd=self.__lastDelta.magnitude()
	    self.__engineNoise.pitch = max(((spd/300.0)+0.67, self.thrust/self.__class__.MAX_THRUST))
	    if self.__engineNoise.snd is WIND_SND:
		    self.__engineNoise.volume=min(spd, self._pos.y)/100.0

	    if self.__play_tire:
		    self.tireSlot.play(pos=self.getPos())
		    self.__play_tire=False

    def serialise(self):
        ser=Mirrorable.serialise(self)
        p=self.getPos()
        ser.append(p.x)
        ser.append(p.y)
        ser.append(p.z)
        a=self.getAttitude()
        ser.append(a.w)
        ser.append(a.x)
        ser.append(a.y)
        ser.append(a.z)
	#print 'MyAirfoil.serialise: '+str((a.w, a.x, a.y, a.z))
	v=self.getVelocity()
	ser.append(v.x)
	ser.append(v.y)
	ser.append(v.z)
        ser.append(self.thrust)
        return ser

    def deserialise(self, ser, estimated=False):
        (px, py, pz)=ControlledSer.vAssign(ser, ControlledSer._POS)
        (aw, ax, ay, az)=ControlledSer.qAssign(ser, ControlledSer._ATT)
        (vx, vy, vz)=ControlledSer.vAssign(ser, ControlledSer._VEL)
        
	#print 'MyAirfoil.deserialise: '+str((aw, ax, ay, az))
        obj=Mirrorable.deserialise(self, ser, estimated).setPos(Vector3(px,py,pz)).setAttitude(Quaternion(aw,ax,ay,az)).setVelocity(Vector3(vx, vy, vz))
	obj.thrust=ser[MyAirfoil._THRUST]

        if not estimated:
            now=manage.now
            period=now-self.__lastUpdateTime
	    if period>0:
		    pos=Vector3(px,py,pz)
		    self.__lastDelta=(pos-self.__lastKnownPos)/period
		    self.__lastUpdateTime=now
		    self.__lastKnownPos=pos
	return obj

    def _hitGround(self):
	    Airfoil._hitGround(self)
	    if self._velocity:
		    self.__play_tire=True
		    self.markChanged(full_ser=True)

    def serNonDroppable(self):
	    self._flags &= ~self.DROPPABLE_FLAG
	    return [ self.__play_tire ]

    def deserNonDroppable(self, play_tire):
	    self.__play_tire=play_tire
	    return self

man=manage
def init():
        #try:
        #        import psyco
        #except ImportError:
	#	print "failed to import psyco\n"
        #        pass
        #else:
	#	print "running psyco\n"
        #        psyco.full()

        parser = optparse.OptionParser()
        option = parser.add_option
        option('-z', '--width', dest='width', type='int', default=3000,
                help='Overall width of the generated terrain')

        option('-2', '--two', dest='two_player', action='store_true', default=False,
                help='Two player split screen action')
        option('-S', '--server', dest='server', type='str', default=None,
                help='Create a server using at this IP / domain')
        option('-C', '--client', dest='client', type='str', default=None,
                help='Create a client connection this a server at this IP / domain')
        man.opt, args = parser.parse_args()
        if args: raise optparse.OptParseError('Unrecognized args: %s' % args)

	factory=SerialisableFact({ MyAirfoil.TYP: MyAirfoil, Bullet.TYP: Bullet })
	if man.opt.server is None:
		if man.opt.client is None:
			man.server=Server()
			man.proxy=Client(factory=factory)
		else:
			man.proxy=Client(server=man.opt.client, factory=factory)
	else:
		if man.opt.client is None:
			man.server=Server(server=man.opt.server, own_thread=False)
			exit(0)
		else:
			man.server=Server(server=man.opt.server)
			man.proxy=Client(server=man.opt.client, factory=factory)
	Sys.init(man.proxy)

	global mouse_cap, fullscreen, views, planes, bots, skybox
	mouse_cap=True
	fullscreen=True
	views = []

        clock = pyglet.clock.Clock()
	loadTerrain()
        r = 0.0

	planes = {}
	plane_inits=[(Point3(0.0,100.0,0.0), 
		      Quaternion.new_rotate_axis(0, Y_UNIT), 
		      Vector3(60,0,0),
		      0),
		     (Point3(-100,200.0,0), 
		      Quaternion.new_rotate_axis(-math.pi/4, Y_UNIT), 
		      Vector3(0,0,0),
		      0)]

	plane_ids=[]
	if man.opt.two_player==True:
		num_players=2
	else:
		num_players=1
	for i in range(num_players):
		(pos, att, vel, thrust)=plane_inits[i]
		print 'att: '+str(att)
		plane = MyAirfoil(pos=pos, attitude=att, velocity=vel, thrust=thrust, proxy=man.proxy)
		plane_ids.append(plane.getId())
		planes[plane.getId()]=plane
		view = View(plane, num_players, man.opt)
		views.append(view)

	if man.opt.two_player==True:
		num_players=2
	else:
		num_players=1
	scale=3.0

	def genMeshArgs(moving_maps, onlys, scale, group):
		all=[("data/models/cockpit/*.csv", (mesh.Mesh, scale, group))]
		all.extend(moving_maps.items())

		movingAndOnly=moving_maps.keys()[:]
		movingAndOnly.append(onlys)

		return (all, movingAndOnly)

	internal_grp=1
	external_grp=2
	(all_internal, internal_only)=genMeshArgs({
		"data/models/cockpit/Plane.004.csv": (mesh.CompassMesh, scale, None),
		"data/models/cockpit/Plane.003.csv": (mesh.AltMeterMesh, scale, None), 
		"data/models/cockpit/Plane.005.csv": (mesh.ClimbMesh, scale, None), 
		"data/models/cockpit/Plane.011.csv": (mesh.RPMMesh, scale, None), 
		"data/models/cockpit/Plane.006.csv": (mesh.AirSpeedMesh, scale, None),
		"data/models/cockpit/Circle.007.csv": (mesh.WingAirSpeedMesh, scale, None),
		"data/models/cockpit/Plane.014.csv": (mesh.BankingMesh, scale, None)
		}, "data/models/cockpit/I_*.csv", scale, internal_grp)

	(all_external, external_only)=genMeshArgs({
		"data/models/cockpit/E_Prop.csv": (mesh.PropMesh, scale, None),
		"data/models/cockpit/E_PropBlend.csv": (mesh.PropBlendMesh, scale, None)
		}, "data/models/cockpit/E_*.csv", scale, external_grp)
	#must use an association list to map glob paths to (mesh, scale) couples instead of a dict
	#as earlier mappings are superceded by later mappings --- so the order is important. dicts
	#do not maintain ordering
	mesh.loadMeshes({ (MyAirfoil.TYP, EXTERNAL): (all_external, internal_only),
			  (MyAirfoil.TYP, INTERNAL): (all_internal, external_only)
			  }, views)
	bots=[]
	skybox = Skybox()
	start_time=time.time()
	print 'startup current ctx: '+str(glx.glXGetCurrentContext())
	return num_players, plane_ids, start_time

def ptrOn(st=True):
	# kw. set_exclusive_mouse called twice due to Pyglet bug in X windows.
	# Pyglet only does something in set_exclusive_mouse if the new st
	# != to the previous st.
	# However when fullscreen is enabled mouse ptr appears without Pyglet
	# updating its internal state so we call set_exclusive_mouse first with
	# the wrong st. This updates the internal st to a different value to the
	# st that we provide in our 2nd invocation of set_exclusive_mouse so
	# the 2nd invocation always does something. Ta da
	win.set_exclusive_mouse(not st)	
	win.set_exclusive_mouse(st)	

def resize(width, height):
	for view in views:
		view.updateDimensions()
	return pyglet.event.EVENT_HANDLED

def setupWin(num_players, plane_ids, fs=True, w=800, h=600):
	config_template=pyglet.gl.Config(double_buffer=True, depth_size=24)
	global win
	if fs:
		win = pyglet.window.Window(fullscreen=True, config=config_template)
	else:
		win = pyglet.window.Window(width=w, height=h, resizable=False, config=config_template)
	win.set_vsync(False)
	win.on_resize=resize       
	global win_ctrls
	win_ctrls=Controller([(Controller.TOG_MOUSE_CAP, KeyAction(key.M, onPress=True)),
			      (Controller.TOG_FULLSCREEN, KeyAction(key.F, onPress=True)),
			      (Controller.TOG_SOUND_EFFECTS, KeyAction(key.N, onPress=True))], win)
	
	global player_keys
	player_keys = []
	if num_players==2:
		player_keys.extend([Controller([(Controller.THRUST, KeyAction(key.E, key.Q)),
						(Controller.FIRE, KeyAction(key.R)),
						(Controller.PITCH, KeyAction(key.S, key.W)),
						(Controller.ROLL, KeyAction(key.A, key.D)),
						(Controller.CAM_FIXED, KeyAction(key._1)),
						(Controller.CAM_FOLLOW, KeyAction(key._2)),
						(Controller.CAM_INTERNAL, KeyAction(key._3)),
						(Controller.CAM_Z, KeyAction(key.C, key.V)),
						(Controller.CAM_X, KeyAction(key.Z, key.X)),
						(Controller.CAM_ZOOM, KeyAction(key.G, key.H)),
						(Controller.CAM_MOUSE_LOOK_X, NULL_ACTION),
						(Controller.CAM_MOUSE_LOOK_Y, NULL_ACTION)], 
			       win),
				    Controller([(Controller.THRUST, KeyAction(key.PAGEDOWN, key.PAGEUP)),
						(Controller.FIRE, MouseButAction(MouseButAction.LEFT)),
						(Controller.CAM_FIXED, KeyAction(key._8)),
						(Controller.CAM_FOLLOW, KeyAction(key._9)), 
						(Controller.CAM_INTERNAL, KeyAction(key._0)), 
						(Controller.PITCH, MouseAction(-0.00010, MouseAction.Y)),
						(Controller.ROLL, MouseAction(-0.00010, MouseAction.X)),
						(Controller.CAM_X, KeyAction(key.O, key.P)), 
						(Controller.CAM_Z, MouseAction(-0.0025, MouseAction.Z)),
						(Controller.CAM_ZOOM, KeyAction(key.J, key.K)),
						(Controller.CAM_MOUSE_LOOK_X, NULL_ACTION),
						(Controller.CAM_MOUSE_LOOK_Y, NULL_ACTION)], 
					      win)])
	else:
			player_keys.append(Controller([(Controller.THRUST, KeyAction(key.E, key.Q)),
						       (Controller.FIRE, MouseButAction(MouseButAction.LEFT)),
						       (Controller.PITCH, KeyAction(key.S, key.W)),
						       (Controller.ROLL, KeyAction(key.A, key.D)),
						       (Controller.CAM_FIXED, KeyAction(key._1)),
						       (Controller.CAM_FOLLOW, KeyAction(key._2)),
						       (Controller.CAM_INTERNAL, KeyAction(key._3)),
						       (Controller.CAM_Z, KeyAction(key.C, key.V)),
						       (Controller.CAM_X, KeyAction(key.Z, key.X)),
						       (Controller.CAM_ZOOM, KeyAction(key.G, key.H)),
						       (Controller.CAM_MOUSE_LOOK_X, MouseAction(-0.00003, MouseAction.X)),
						       (Controller.CAM_MOUSE_LOOK_Y, MouseAction(-0.00002, MouseAction.Y))],
		       win))
	for i in range(num_players):
		print 'planes: '+str(planes)+' '+str(player_keys[i])
		planes[plane_ids[i]].setControls(player_keys[i])
		views[i].setViewController(win, player_keys[0])


	glClearColor(Skybox.FOG_GREY, Skybox.FOG_GREY, Skybox.FOG_GREY, 1.0)
	glClearDepth(1.0)
	glColorMaterial(GL_FRONT, GL_AMBIENT_AND_DIFFUSE)
	glEnable(GL_COLOR_MATERIAL)
	glEnable(GL_LIGHT0)
	fourfv = ctypes.c_float * 4        
	glLightfv(GL_LIGHT0, GL_AMBIENT, fourfv(0.1, 0.1, 0.1, 1.0))
	glLightfv(GL_LIGHT0, GL_DIFFUSE, fourfv(0.6, 0.6, 0.6, 1.0))
	glLightfv(GL_LIGHT0, GL_SPECULAR, fourfv(0.05, 0.05, 0.05, 1.0))
	lightPosition = fourfv(0.0,1000.0,1.0,1.0)
	glLightfv(GL_LIGHT0, GL_POSITION, lightPosition)	
	mesh.object3dLib.setLightPosition(lightPosition)
	glEnable(GL_DEPTH_TEST)
	glEnable(GL_CULL_FACE)
	glDepthFunc(GL_LEQUAL)
	glShadeModel(GL_SMOOTH)
	glEnable(GL_BLEND)
	glEnable(GL_POINT_SMOOTH)
	glPointSize(2)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

	glEnable(GL_FOG)

def timeSlice(dt):
	try:
		if man.proxy.alive():
			man.updateTime()
			[ plane.update() for plane in planes.itervalues() if plane.alive() ]
			[ b.update() for b in set(Bullet.getInFlight())]

			if man.proxy.acquireLock():
				bots[:]= man.proxy.getTypesObjs([ MyAirfoil.TYP, Bullet.TYP ]) 
				[ b.estUpdate() for b in bots ]
				man.proxy.releaseLock()
			
			[ plane.markChanged() for plane in planes.itervalues() if plane.alive() ]
			[ b.markChanged() for b in Bullet.getInFlight() if b.justBornOrDead() ]

			if win.has_exit:
				print 'exiting window'
				for obj in planes.itervalues():
					obj.markDead()
					obj.markChanged()
				man.proxy.markDead()
				man.proxy.markChanged()

			events=win_ctrls.eventCheck()
			if events[Controller.TOG_MOUSE_CAP]!=0:
				global mouse_cap
				mouse_cap = not mouse_cap
				ptrOn(mouse_cap)
			if events[Controller.TOG_FULLSCREEN]!=0:
				global fullscreen
				fullscreen = not fullscreen
				mesh.deleteVBOs()
				glFinish()
				#win.set_fullscreen(fullscreen)
				#pyglet.app.exit()
				win.dispatch_event('on_close')
				return
			if events[Controller.TOG_SOUND_EFFECTS]!=0:
				SoundSlot.sound_toggle()
			win_ctrls.clearEvents()

			#glClear(GL_DEPTH_BUFFER_BIT)
			glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)

    			[ plane.eventCheck() for plane in planes.itervalues() if plane.alive() ]
			for view in views:
				glLoadIdentity()
				view.activate()
				if view.getPlaneId() in planes:
					my_plane=planes[view.getPlaneId()]
					#view.printToScreen('pos = ' + str(my_plane.getPos()))
					#view.printToScreen('bank = ' + str('%f' % my_plane.getAttitude().get_bank()))
					#view.printToScreen('vel = ' + str(my_plane.getVelocity()))
					#view.printToScreen('thrust = ' + str(my_plane.thrust))
					#view.printToScreen('airspeed = ' + str(my_plane.getAirSpeed()))
					#view.printToScreen("heading = " + str(my_plane.getHeading()/math.pi*180.0))

				skybox.draw(view)
				drawTerrain(view)

				#draws should precede plne.eventCheck to ensure correct frame_rot is used
				for bot in bots:
					if bot.alive():
						mesh.draw(bot, view)
				Bullet.drawAll()
				
				view.eventCheck()
				glLoadIdentity()
				view.drawText()
				#dt=clock.tick()

			setListener(views[0].getEye(), views[0].getPos(), views[0].getZen())

			if manage.sound_effects:
				for bot in bots:
					if not bot.alive():
						if bot.getId() in planes:
							del planes[bot.getId()]
					else:
						bot.play()
			else:
				for bot in bots:
					if bot.getId() in planes and not bot.alive():
							del planes[bot.getId()]

			return
		
	except Exception as detail:
		print str(detail)
		traceback.print_exc()
		man.proxy.markDead()
		man.proxy.markChanged()

#def main_next(dt):
#	main_iter.next()

def run():
	num_players, plane_ids, start_time=init()
	#pyglet.clock.schedule_interval(timeSlice, 1/60.0)
	pyglet.clock.schedule(timeSlice)
	while man.proxy.alive():
		setupWin(num_players, plane_ids, fs=fullscreen)
		glFinish()
		mesh.createVBOs(mesh.vbo_meshes)
		glFinish()
		ptrOn(mouse_cap)
		pyglet.app.run()
		glFinish()

	flush_start=time.time()
	while not man.proxy.attemptSendAll():
		if time()-flush_start>3:
			break
		sleep(0)
	man.proxy.join(3)
	try:
		assert not man.proxy.isAlive()
	except:
		print_exc()
	if man.server:
		man.server.join(3)
		try:
			assert not man.server.isAlive()
		except:
			print_exc()
	mesh.deleteMeshes()
	print 'quitting main thread'
        print "fps:  %d" % clock.get_fps()
	end_time=time.time()
	if man.proxy:
		print "client: kb/s read: "+str((man.proxy.bytes_read/1024)/(end_time-start_time))+' sent: '+str((man.proxy.bytes_sent/1024)/(end_time-start_time))
	if man.server:
		print "server: kb/s read: "+str((man.server.bytes_read/1024)/(end_time-start_time))+' sent: '+str((man.server.bytes_sent/1024)/(end_time-start_time))
	if SerialisableFact.TOT_CNT>0:
		print 'hits: '+str(SerialisableFact.HIT_CNT)+' '+str(SerialisableFact.TOT_CNT)+' ratio: '+str(SerialisableFact.HIT_CNT/float(SerialisableFact.TOT_CNT))
	else:
		print 'hits: '+str(SerialisableFact.HIT_CNT)+' '+str(SerialisableFact.TOT_CNT)


if __name__ == '__main__':
	cProfile.run('run()', 'profile')
	#run()

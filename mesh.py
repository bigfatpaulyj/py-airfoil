import ctypes
from ctypes import *
from euclid import *
import glob
import itertools
from math import cos, degrees, sin
import manage
from pyglet.gl import *
import os
import sys
from traceback import print_exc

import manage
from pyglet import image
from pyglet.gl import *

QUART_PI=0.25*math.pi
HALF_PI=0.5*math.pi
PI2=2*math.pi
global object3dLib
if os.name == 'nt':
    object3dLib = cdll.LoadLibrary("bin\object3d.dll")
else:
    object3dLib = cdll.LoadLibrary("bin/object3d.so")

object3dLib.load.argtypes=[ c_char_p, c_float ]
object3dLib.load.restype=c_void_p

object3dLib.deleteMesh.argtypes=[ c_void_p ]
object3dLib.deleteMesh.restype=None

object3dLib.getUvPath.argtypes=[ c_void_p, c_uint ]
object3dLib.getUvPath.restype=c_char_p

object3dLib.getMeshPath.argtypes=[ c_void_p ]
object3dLib.getMeshPath.restype=c_char_p

object3dLib.setTexId.argtypes=[ c_void_p, c_uint, c_uint ]
object3dLib.setTexId.restype=c_uint

object3dLib.createTexture.argtypes=[ c_void_p, c_uint, c_void_p, c_uint, c_uint, c_uint ]
object3dLib.createTexture.restype=c_uint

object3dLib.draw.argtypes=[ c_void_p ]
object3dLib.draw.restype=None

pos_rot_unchanged=False
def setPosRotUnchanged(flag):
    global pos_rot_unchanged
    pos_rot_unchanged=flag
    return True
    
last_cams={}
def draw(bot, view):
    v_type=view.getPlaneView(bot.getId())
    if (bot.TYP, v_type) in meshes:
        angleAxis = (bot.getAttitude() * Quaternion(0.5, -0.5, 0.5, 0.5) ).get_angle_axis()
        axis = angleAxis[1].normalized()

        fpos = (c_float * 3)()
        fpos[0] = bot._pos.x
        fpos[1] = bot._pos.y
        fpos[2] = bot._pos.z
        object3dLib.setPosition(fpos)

        fpos[0] = axis.x
        fpos[1] = axis.y
        fpos[2] = axis.z

        object3dLib.setAngleAxisRotation(c_float(degrees(angleAxis[0])), fpos)
        try:
            assert setPosRotUnchanged(True)
            for m in meshes[(bot.TYPE, v_type)]:
                glPushMatrix()
                m.draw(bot, view.view_id)
                glPopMatrix()
        except AssertionError:
            print_exc()
            sys.exit(-1)
    else:
        glPushMatrix()
        bot.draw()
        glPopMatrix()

def loadMeshes(mesh_paths, views):
    lookup = {}
    global meshes
    meshes = {}
    global name_to_mesh
    name_to_mesh = {}
    paths = {}
    if os.name == 'nt':
        convert=lambda s: re.sub(r'/', r'\\', s)
    else:
        convert=lambda s: s

    def genGlobbedList(glob_path, cls, scale, blacklisted):
        globs=glob.glob(convert(glob_path))
        return [ (path, (cls, scale)) for path in globs if path not in blacklisted]

    for mesh_key in mesh_paths:
        all_possible_globs=mesh_paths[mesh_key][0]
        blacklist=list(itertools.chain(*[ glob.glob(convert(black_glob)) for black_glob in mesh_paths[mesh_key][1]]))
        paths[mesh_key]=dict(itertools.chain(*[ genGlobbedList(glob_path, cls, scale, blacklist) for (glob_path, (cls, scale)) in all_possible_globs ])).items()

    for mesh_key in mesh_paths:
        meshes[mesh_key]=[ cls(object3dLib.load(path, scale), views, mesh_key) for (path, (cls, scale)) in paths[mesh_key] ]

    #draw function assumes that Mesh instances are first in the meshes values lists
    #so reorder
    for mesh_key in meshes:
        unordered_meshes=meshes[mesh_key]
        meshes[mesh_key]=[]
        for m in unordered_meshes:
            if type(m) is Mesh:
                meshes[mesh_key].append(m)
        for m in unordered_meshes:
            if type(m) is not Mesh:
                meshes[mesh_key].append(m)

all_meshes=[]
def deleteMeshes():
    for mesh in all_meshes:
        object3dLib.deleteMesh(mesh)

class Mesh(object):
    def __init__(self, mesh, views, mesh_key):
        self.mesh=mesh
        self.key=mesh_key
        all_meshes.append(mesh)
        global name_to_mesh
        if mesh_key in name_to_mesh:
            self._sibs=name_to_mesh[mesh_key]
        else:
            self._sibs={}
            name_to_mesh[mesh_key]=self._sibs
        self._mesh_path=object3dLib.getMeshPath(self.mesh)
        self._sibs[self._mesh_path]=self
            
        # self.textures exists only to maintain a reference to the textures, ensuring that it isn't deleted during garbage collection
        self.textures=[]

        self.upload_textures()
        for v in views:
            v.push_handlers(self)
        self._bot_details={}
        self.rot=0.0

    def __str__(self):
        return object.__str__(self)+': '+self._mesh_path

    def test_draw(self, bot):
        glPushMatrix()
        glLoadIdentity()
        #glTranslatef(bot._pos.x, bot._pos.y, bot._pos.z)
        
        #new stuff
        glDisable( GL_DEPTH_TEST);
        glDisable(GL_FOG);
        glDisable( GL_LIGHTING);
        glBegin(GL_QUADS)
        glColor3f(1.0 ,1.0 ,0.0)
        scaler=50.0
        glVertex3f(-1.0*scaler, 1.0*scaler, 1.0*scaler-100)
        glVertex3f( 1.0*scaler, 1.0*scaler, 1.0*scaler-100)
        glVertex3f( 1.0*scaler, 1.0*scaler,-1.0*scaler-100)
        glVertex3f(-1.0*scaler, 1.0*scaler,-1.0*scaler-100)
        glEnd()
        glEnable( GL_DEPTH_TEST)
        glPopMatrix()
        
    def upload_textures(self):
        uvId=0
        c_path=object3dLib.getUvPath(self.mesh, uvId)
        while c_path!=None:
            path=c_path
            img=image.load(path)
            tex=img.get_texture()
            self.textures.append(tex)
            #print "upload_textures: "+str(tex.target)+" id: "+str(tex.id)+" tex: "+str(tex.get_texture())+" coords: "+str(tex.tex_coords)
            object3dLib.setTexId(self.mesh, uvId, tex.id)
            #object3dLib.createTexture(self.mesh,
            #                          uvId, img.get_data('RGBA', img.width*len('RGBA')), img.width, img.height, GL_RGBA)
            uvId+=1
            c_path=object3dLib.getUvPath(self.mesh, uvId)

    def view_change(self, view):
        new_details={}
        for (view_id, bot_id) in self._bot_details:
            if view_id is not view:
                new_details[(view_id, bot_id)]=self._bot_details[(view_id, bot_id)]
        self._bot_details=new_details

    def draw(self, bot, view_id):
        assert pos_rot_unchanged
        object3dLib.draw(self.mesh)

    def drawRotated(self, bot, angle_quat, drawing_mesh, centre_mesh):
        assert setPosRotUnchanged(False)
        att=bot.getAttitude()
        axisRotator=Quaternion(0.5, -0.5, 0.5, 0.5)
        angleAxis= (att * angle_quat * axisRotator ).get_angle_axis()
        
        mid = (c_float * 3)()
        object3dLib.getMid(centre_mesh, mid)
        midPt=Vector3(mid[0], mid[1], mid[2])
        rotOrig=(att * axisRotator * (midPt))
        rotNew=(att * angle_quat * axisRotator * (midPt))

        axis = angleAxis[1].normalized()
        c=bot.getPos()-(rotNew-rotOrig)
        
        fpos = (c_float * 3)()
        fpos[0] = c.x
        fpos[1] = c.y
        fpos[2] = c.z
        object3dLib.setPosition(fpos)
        
        fpos[0] = axis.x
        fpos[1] = axis.y
        fpos[2] = axis.z
        
        object3dLib.setAngleAxisRotation(c_float(degrees(angleAxis[0])), fpos)
        object3dLib.draw(drawing_mesh)

        # glPushMatrix()
        # glLoadIdentity()
        # #att=bot.getAttitude()
        # #axisRotator=Quaternion(0.5, -0.5, 0.5, 0.5)
        # axisRotator=Quaternion(0.0, 0.0, 0.71, 0.71)
        # angleAxis= (angle_quat * axisRotator ).get_angle_axis()
        
        # mid = (c_float * 3)()
        # object3dLib.getMid(centre_mesh, mid)
        # midPt=Vector3(mid[0], mid[1], mid[2]) * 100.0
        # rotOrig=(axisRotator * (midPt))
        # rotNew=(angle_quat * axisRotator * (midPt))

        # axis = angleAxis[1].normalized()
        # #c=bot.getPos()-(rotNew-rotOrig)
        # c=-(rotNew-rotOrig)
        
        # fpos = (c_float * 3)()
        # fpos[0] = c.x
        # fpos[1] = c.y
        # fpos[2] = c.z
        # object3dLib.setPosition(fpos)
        
        # fpos[0] = axis.x
        # fpos[1] = axis.y
        # fpos[2] = axis.z
        
        # object3dLib.setAngleAxisRotation(c_float(degrees(angleAxis[0])), fpos)
        # object3dLib.draw(drawing_mesh)
        # glPopMatrix()
                        
class PropMesh(Mesh):
    def __init__(self, mesh, views, key):
        print 'PropMesh.__init__'
        Mesh.__init__(self, mesh, views, key)
        self.ang=0.0
        
    def draw(self, bot, view_id):
        thrust_prop=int(bot.thrust / (bot.MAX_THRUST/100))
        if thrust_prop!=0:
            self.ang+=manage.delta*thrust_prop
            self.ang %= PI2
        #self.ang=self.ang+this_ang
        #if self.ang>=PI2:
        #    self.ang-=PI2
        #print 'thrust_prop: '+str(thrust_prop)+' ang: '+str(ang)
        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, 0.0, -self.ang), self.mesh, self._sibs['data/models/cockpit/E_PropPivot.csv'].mesh)

class AltMeterMesh(Mesh):
    def __init__(self, mesh, views, key):
        Mesh.__init__(self, mesh, views, key)

    def draw(self, bot, view_id):
        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, 0.0, ((bot.getPos().y % 6154.0)/6154)*(PI2)), self.mesh, self._sibs['data/models/cockpit/AltDial.csv'].mesh)

class ClimbMesh(Mesh):
    def __init__(self, mesh, views, key):
        Mesh.__init__(self, mesh, views, key)

    def draw(self, bot, view_id):
        ident=bot.getId()
        if (view_id, ident) not in self._bot_details:
            self._bot_details[(view_id, ident)]=(manage.now, 0.0)

        (last_update, smoothed_rate) = self._bot_details[(view_id, ident)]
        interval=manage.now-last_update
        if interval>1:
            interval=1.0

        smoothed_rate+=(bot.getVelocity().y-smoothed_rate)*interval

        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, 0.0, ((smoothed_rate % 300)/300)*(PI2)), self.mesh, self._sibs['data/models/cockpit/Circle.002.csv'].mesh)

        self._bot_details[(view_id, ident)]=(manage.now, smoothed_rate)

class BankingMesh(Mesh):
    def __init__(self, mesh, views, key):
        Mesh.__init__(self, mesh, views, key)

    def draw(self, bot, view_id):
        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, 0.0, -(bot.getAttitude().get_bank())), self.mesh, self._sibs['data/models/cockpit/LRDial.csv'].mesh)

#class RollingMesh(Mesh):
#    def __init__(self, mesh, views):
#        Mesh.__init__(self, mesh, views)
#
#    def draw(self, bot, view_id):
#        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, 0.0, (bot.getAttitude().get_bank())), self.mesh, self._sibs['data/models/cockpit/Cylinder.csv'].mesh)

class AirSpeedMesh(Mesh):
    def __init__(self, mesh, views, key):
        Mesh.__init__(self, mesh, views, key)

    def draw(self, bot, view_id):
        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, 0.0, (bot.getVelocity().magnitude()/200.0) * PI2), self.mesh, self._sibs['data/models/cockpit/Circle.003.csv'].mesh)

class WingAirSpeedMesh(Mesh):
    def __init__(self, mesh, views, key):
        Mesh.__init__(self, mesh, views, key)

    def draw(self, bot, view_id):
        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, -(bot.getVelocity().magnitude()/200.0) * QUART_PI, 0.0), self.mesh, self._sibs['data/models/cockpit/Circle.008.csv'].mesh)

class RPMMesh(Mesh):
    def __init__(self, mesh, views, key):
        Mesh.__init__(self, mesh, views, key)

    def getRPMFraction(self, bot):
        # 195 max vel when level at full thrust
        if bot.thrust==0:
            return 0.0
        #return (bot.getVelocity().magnitude()/max_vel + t/bot.MAX_THRUST)*0.3
        #print 'rpm. '+str((bot.getVelocity().magnitude()/195.0 + (t/bot.MAX_THRUST)*6)/6)+' vel: '+str((t/bot.MAX_THRUST)*6)+' thrust: '+str(bot.getVelocity().magnitude()/max_vel)
        return (bot.getVelocity().magnitude()/195.0 + (bot.thrust/bot.MAX_THRUST)*2)/3

    def draw(self, bot, view_id):
        self.drawRotated(bot, Quaternion.new_rotate_euler(0.0, 0.0, self.getRPMFraction(bot) * math.pi), self.mesh, self._sibs['data/models/cockpit/Circle.004.csv'].mesh)

class CompassMesh(Mesh):
    def __init__(self, mesh, views, key):
        Mesh.__init__(self, mesh, views, key)

    def draw(self, bot, view_id):
        heading=bot.getHeading()
        ident=bot.getId()
        if (view_id, ident) not in self._bot_details:
            self._bot_details[(view_id, ident)]=(heading, 0.0, manage.now)

        (last_heading, speed, last_update) = self._bot_details[(view_id, ident)]

        #handle wrapping by calculating the heading when greating than last_heading and when less
        if heading > last_heading:
            alt_heading = heading - PI2
        else:
            alt_heading = heading + PI2
        if math.fabs(heading - last_heading) > math.fabs(alt_heading - last_heading):
            heading=alt_heading

        interval=manage.now-last_update
        if heading > last_heading:
            if speed>=0:
                speed += interval*0.00075
            else:
                speed += interval*0.001            
        else:
            if heading < last_heading:
                if speed<=0:
                    speed -= interval*0.00075
                else:
                    speed -= interval*0.001
        spd_limit=math.pi/14 * interval
        #print 'comp: last: '+str(last_heading)+' cur: '+str(heading)+' spd: '+str(speed)+' tm: '+str(manage.now-last_update)+' ltd: '+str(spd_limit)
        if speed>spd_limit:
            #print 'hit spd_limit 1: '+str(interval)+' now: '+str(manage.now)+' last: '+str(last_update)
            speed=spd_limit
        else:
            if speed<-spd_limit:
                #print 'hit spd_limit 2: '+str(interval)
                speed=-spd_limit
        last_heading+=speed
        last_heading = last_heading % PI2
        last_update=manage.now
        self.drawRotated(bot, Quaternion.new_rotate_euler(-last_heading, 0.0, 0.0), self.mesh, self._sibs['data/models/cockpit/Cylinder.002.csv'].mesh)
        self._bot_details[(view_id, ident)]=(last_heading, speed, last_update)

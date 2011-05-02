#include "cterrain.h"

int terrain_max_x=0;	//max size of terrain map data array in x direction
int terrain_max_z=0;	//max size of terrain map data array in z direction
terrain_mesh_point *terrain;
ubyte default_map_y;		//the y value of map that is used when we run out of map definition data. this is to be loaded from map definition file
float default_map_intensity;	//this is needed so that the colour of the default map parts match with the normal map colours
gl_col* colr_ref = NULL;
int elev_var=63;		//max view triangle's centre point retraction when looking up or down (old value 82)
//float map_expansion_const;
int fog_dist;			//dist fog ends at. calculated during view triangle calculations
gl_col backgr={1.0,1.0,1.0};
//float y_scale_const;
int drawnQuads = 0;
int map_precision=1; //how many points to skip in the map file
gl_col backg;				//the background colour. to be loaded from map
int terrain_size;
terrain_tile hmap_tile = {0};
float aspectRatio;
bool wireframe = true;
float map_expansion_const = 1.0f; //how much the multiply the x and z coords by before plotting
float y_scale_const = .02f*32.0f/32;	//how much to scale the y values before plotting


// Export an interface with standard C calling conventions so that it can 
// be called in a standard way across different platforms.
extern "C" 
{
	DLL_EXPORT void init(char *colourRefFilename, char *mapFilename, float aspectRatioArg, bool wireframeArg, float scale, float yScale)
	{
		wireframe = wireframeArg;
		map_expansion_const = scale;
		y_scale_const = yScale;
		aspectRatio = aspectRatioArg;
		load_hm_colour_ref(colourRefFilename);
		preloadTerrain(mapFilename);
	}

	DLL_EXPORT void initDefault()
	{		
		init ("strip1.bmp", "map_output.hm2", 4.0f/3.0f, wireframe, map_expansion_const, y_scale_const);
	}

	DLL_EXPORT void draw(float povArg[])
	{
		//point_of_view *pov =(point_of_view *)povArg;
		point_of_view pov;		
		float viewVector[3];
		viewVector[0] = povArg[3] - povArg[0];
		viewVector[1] = povArg[4] - povArg[1];
		viewVector[2] = povArg[5] - povArg[2];
		pov.x = povArg[0];
		pov.y = povArg[1];
		pov.z = povArg[2];
		// Calculate the distance from the origin to the viewVector projected onto the ground plane.
		float dist = sqrt(sqr(viewVector[0]) + sqr(viewVector[2]));
		pov.ax = getAngleForXY(dist, viewVector[1]);
		pov.ay = -getAngleForXY(viewVector[2], viewVector[0]); // 0 radians points down the positive Z-axis
		pov.az = 0;

		terDrawLandscape(pov, aspectRatio, 1);	
	}
}

float getAngleForXY(float adj, float opp)
{
	float angle = 0.0f;
	if (0.0f == adj)
	{
		angle = PI / 2.0f;
	}
	else
	{
		angle = atan(abs(opp/adj));
	}
	
	if (adj <= 0.0f && opp >= 0.0f)
	{
		angle = PI - angle;
	}
	else if (adj <= 0.0f && opp < 0.0f)
	{
		angle = PI + angle;
	}
	else if (adj > 0.0f && opp < 0.0f)
	{
		angle = 2.0f * PI - angle;
	}

	return angle;
}

void errorMsg(char *msg,int error_type) {
	if (error_type>=0) {
		fprintf(stderr,"Non-Fatal Error %i: %s\n",error_type,msg);
		printf("Non-Fatal Error %i: %s\n",error_type,msg);
	}
	else {
	fprintf(stderr,"Fatal Error %i: %s\nTerminating.\n",-error_type,msg);
	printf("Fatal Error %i: %s\nTerminating.\n",-error_type,msg);
	exit(-1);
	}
}

int fscanint(FILE* fin) {
	//reads a single integer from a file..which was 
	//written using fprintint()
	int in;
	int i;
	for (i=0;i<sizeof(int);i++) {
		fscanf(fin,"%c", ((char*)(&in))+i );
	}

	return in;
}

int preloadTerrain(char *fname) {
	FILE *fptr;
	int dims[2]={-1};
	int x,z,i,j;
	byte_ptr input_file;
	fptr = fopen(fname,"rb");
	int size;
	short* hfield;

	// Delete old heightmap if it exists
	if (hmap_tile.hfield != NULL)
	{
		delete hmap_tile.hfield;
		hmap_tile.hfield = NULL;
	}

	if (fptr==NULL) {errorMsg("Cant find the heightmap.",1);return FALSE;}
	if ( !(strstr(fname,".hmp")) && !(strstr(fname,".hm2")) ) {
		errorMsg("Wrong file extension while loading heightmap.",1);
		return FALSE;
	}
	
	if (strstr(fname,".hm2")!=NULL) {
		
		size=fscanint(fptr);
		size=fscanint(fptr);
		map_precision=fscanint(fptr);
		fgetc(fptr);

		backg.r=1.0f;//must make these map dependent later
		backg.g=1.0f;
		backg.b=1.0f;

		hfield = new short int[size * size];
		
		for (j=0; j<size; j++) {
			for (i=0; i<size; i++) {
				hfield[j*size + i]=fgetc(fptr);
			}
		}
	}
	else {			
		
		fread(dims,4,2,fptr);
		input_file = new ubyte[(dims[0]*dims[1])+92];
		x=dims[0];z=dims[1];
		fread(input_file,1,(x*z) + 92 ,fptr);
				
		map_precision=8;
		size=x/map_precision;
		size=z/map_precision;
		
		hfield = new short int[size * size];

		for (j=0; j<size; j++) {
			for (i=0; i<size; i++) {
				hfield[j*size + i]=				
					*(input_file +92 + j*map_precision*z + i*map_precision);
			}
		}
		
		delete [] input_file;

		backg.r=1.0f;//must make these map dependent later
		backg.g=1.0f;
		backg.b=1.0f;
		
		
	}
	terrain_size=size;

	hmap_tile.dim=map_expansion_const;
	hmap_tile.size=size;
	hmap_tile.hfield=hfield;

	terLoadTerrain(hfield,size,map_expansion_const,y_scale_const);
	fclose(fptr);
	return TRUE;
}

int load_hm_colour_ref(char *fname) {
	FILE *fptr;
	byte_ptr input_file;
	int i;

	// Delete old colour reference array if it exists
	if (colr_ref != NULL)
	{
		delete colr_ref;
		colr_ref = NULL;
	}

	fptr = fopen(fname,"rb");

	if ( fptr == NULL )	
	{
		// Display Error Message And Stop The Function
		fprintf(stderr,"Can't Find The Height Map Colour Reference file!");
		return FALSE;
	}
	input_file = new ubyte[822];
	fread(input_file,1,822,fptr);
	fclose(fptr);

	colr_ref = new gl_col[256];
    
	
	for (i=0; i<256; i+=1) {
		//printf("%x\n",*(input_file+i+54));
		colr_ref[i].b =  (*(input_file+i*3+54))/256.0f;
		colr_ref[i].g =  (*(input_file+i*3+54+1))/256.0f;
		colr_ref[i].r =  (*(input_file+i*3+54+2))/256.0f;
		
	}
	for (i=0;i<256;i++) {
		//printf("%lf,%lf,%lf\n",colour_ref[i].r,colour_ref[i].g,colour_ref[i].b);
	}
	delete [] input_file;

	if (fptr==NULL) return FALSE;
	else return TRUE;
}


//write the actual vertex colours into the terrain in memory
void terPrecalc_vertex_colours() {	
	int x,z;	
	for (x=0;x<terrain_max_x;x++) {
		for (z=0;z<terrain_max_z;z++) {
			terrain_map(x,z).col.r=terMap_col(terrain_map(x,z),'r');
			terrain_map(x,z).col.g=terMap_col(terrain_map(x,z),'g');
			terrain_map(x,z).col.b=terMap_col(terrain_map(x,z),'b');
		}
	}
}

//returns the colour of a vertex in the terrain
//used during map load
//depends on vertex light intensity and vertex altitude
float terMap_col(terrain_mesh_point &terrain, char col) {
	float intensity;
	
	switch (col) {
	case 'r':intensity=terrain.intensity* colr_ref[terrain.y].r;break;
	case 'g':intensity=terrain.intensity* colr_ref[terrain.y].g;break;
	case 'b':intensity=terrain.intensity* colr_ref[terrain.y].b;break;
	default:intensity=0;break;	
	}

	return intensity;
}

int terLoadTerrain(short int*hfield,int size, 
				   float input_map_expansion_const,float input_y_scale) {
	int i,j;
	terrain = new terrain_mesh_point[size * size];
	//map_expansion_const=input_map_expansion_const;
	//y_scale_const=input_y_scale;
	terrain_max_x=size;
	terrain_max_z=size;
	
	for (j=0; j<size; j++) {
		for (i=0; i<size; i++) {
			
			terrain_map(i,j).y=(ubyte) hfield[j*size+i];
			
		}
	}
	
	terPrecalc_vertex_intensities();
	terPrecalc_vertex_colours();

	return true;
}

//precalculate the terrain vertex's light intensities
void terPrecalc_vertex_intensities() {
	
	light_source light;
	int x,z;
	int y[4];
	vector vector_normal;
	vector light_vector;
	vector_dec unit_vector_norm;
	vector_dec unit_light_vector;
	float vector_mag,light_mag,calc_mag;

	light.x=-500;
	light.y=5000;
	light.z=-500;
	light.intensity=1.0f; 

	for (x=0;x<terrain_max_x;x++) {
		for (z=0;z<terrain_max_z;z++) {
			if ((x==0)||(x==terrain_max_x-1)||(z==0)||(z==terrain_max_z-1))
				terrain_map(x,z).intensity=0; //leave a border around the outside to avoide array range errors
			else {
				y[0]=terrain_map(x,z-1).y-terrain_map(x,z).y;
				y[1]=terrain_map(x,z+1).y-terrain_map(x,z).y;
				y[2]=terrain_map(x-1,z).y-terrain_map(x,z).y;
				y[3]=terrain_map(x+1,z).y-terrain_map(x,z).y;

				//calc the normal to the vertex
				//depends on the 4 vertexes around it
				vector_normal.x=(y[3])	+(-y[2])	+(-y[2])	+(y[3]);
				vector_normal.y=(1)		+(1)		+(1)		+(1);
				vector_normal.z=(-y[0])	+(-y[0])	+(y[1])		+(y[1]);

				//calc the magnitude of the vector normal to the vertex
				vector_mag=(float) sqrt((float)(sqr(vector_normal.x)+sqr(vector_normal.y)+sqr(vector_normal.z)));

				//calculate the unit vector normal to the vertex
				unit_vector_norm.x=vector_normal.x/vector_mag;
				unit_vector_norm.y=vector_normal.y/vector_mag;
				unit_vector_norm.z=vector_normal.z/vector_mag;

				//calculate the light vector between the light source and the current vertex
				light_vector.x=light.x-x;
				light_vector.y=light.y-terrain_map(x,z).y;
				light_vector.z=light.z-z;

				//calculate the magnitude of the light vector
				light_mag=(float)sqrt((float)(sqr(light_vector.x)+sqr(light_vector.y)+sqr(light_vector.z)));

				//calculate the unit light vector
				unit_light_vector.x=light_vector.x/light_mag;
				unit_light_vector.y=light_vector.y/light_mag;
				unit_light_vector.z=light_vector.z/light_mag;

				//get: (unit vertex vector normal).(unit light vector) = light intensity magnitude
				calc_mag=	unit_vector_norm.x*unit_light_vector.x+
							unit_vector_norm.y*unit_light_vector.y+
							unit_vector_norm.z*unit_light_vector.z;
				if (calc_mag>.3) calc_mag=.3f; //this makes the incident lighting effect less "shiny"..ie. it scales down the higher incident light intensites
				
				terrain_map(x,z).intensity=ambient_light+
										(float) fabs(light.intensity*(calc_mag));
				if (terrain_map(x,z).intensity>1) terrain_map(x,z).intensity=1;//just checking
				
			}
		}
	}
	//Now redo the similar process to get the default intensity
	//for the area surrounding the map.

	//calculate the unit vector normal to the vertex
	unit_vector_norm.x=0;
	unit_vector_norm.y=1;
	unit_vector_norm.z=0;
	
	//calculate the light vector between the light source and the current vertex
	light_vector.x=light.x;
	light_vector.y=light.y-default_map_y;
	light_vector.z=light.z;
	
	//calculate the magnitude of the light vector
	light_mag=(float)sqrt((float)(sqr(light_vector.x)+sqr(light_vector.y)+sqr(light_vector.z)));
	
	//calculate the unit light vector
	unit_light_vector.x=light_vector.x/light_mag;
	unit_light_vector.y=light_vector.y/light_mag;
	unit_light_vector.z=light_vector.z/light_mag;
	
	//get: (unit vertex vector normal).(unit light vector) = light intensity magnitude
	calc_mag=	unit_vector_norm.x*unit_light_vector.x+
		unit_vector_norm.y*unit_light_vector.y+
		unit_vector_norm.z*unit_light_vector.z;
	if (calc_mag>.3) calc_mag=.3f; //this makes the incident lighting effect less "shiny"..ie. it scales down the higher incident light intensites
	
	default_map_intensity=ambient_light+
		(float) fabs(light.intensity*(calc_mag));
	if (default_map_intensity>1) default_map_intensity=1;//just checking
				
}

void terDrawLandscape(point_of_view &input_pov,float aspect
					  ,short detail_levels) {
	vector point[3];//left,right,centre;
	int cut_off_dist,detail;
	float leftx,rightx,leftm,rightm;
	float view_angle;
	point_of_view pov=input_pov;
	static float persp_angle;
	static short min_detail_level;
	int i,j;

	glEnable(GL_DEPTH_TEST);
	//glDisable(GL_FOG);
	glBegin(  wireframe ? GL_LINES : GL_QUADS);	//start drawing quads


	persp_angle=(float) atan(aspect/2.0f);

	
	//setup initial view angle
	if ((pov.ax>(PI/2.0)) && (pov.ax<=(PI*3.0f/2.0f))) {
		pov.ay+=PI;
	}
	view_angle=(float) -pov.ay;
	
	//vary the cut off distance (and hence fog dist)
	//with altitude nb..i think the cut dist is in quads
	cut_off_dist=(int) ((cut_off_max/2)+alt_var_const*pov.y);
	if (cut_off_dist>cut_off_max) cut_off_dist=cut_off_max;
	fog_dist=(int) (cut_off_dist-alt_var_const*pov.y-20);
	

	//convert the pov coord's to coord's on the terrain map
	pov.x=pov.x/map_expansion_const;
	pov.y=pov.y/map_expansion_const;
	pov.z=pov.z/map_expansion_const;

	//begin populating array of view triangle coords
	//which can sorted later
	point[2].x= (int) pov.x;
	point[2].z= (int) pov.z;
	point[2].y= (int) pov.y;
 
	//pull back the base coord a bit behind the point of view
	point[2].x-=(int)(sin(view_angle)*5);
	point[2].z-=(int)(cos(view_angle)*5);

	//if looking towards the ground, pull back the base coord accordingly
	//also adjust the fog accordingly
	if ((pov.ax>PI)&&(pov.ax<2*PI)) {
		point[2].x+=(int)(sin(view_angle)*((sin(pov.ax)*elev_var)));
		point[2].z+=(int)(cos(view_angle)*((sin(pov.ax)*elev_var)));
		fog_dist+=(int) (sin(pov.ax)*elev_var);
	}

	//populate rest of view triangle coord array
	point[0].x=point[2].x + (int)( cut_off_dist * sin(view_angle-persp_angle));
	point[0].z=point[2].z + (int)( cut_off_dist * cos(view_angle-persp_angle));
	point[1].x=point[2].x + (int)( cut_off_dist * sin(view_angle+persp_angle));
	point[1].z=point[2].z + (int)( cut_off_dist * cos(view_angle+persp_angle));
	
	terSort_view_triangle(point);	//seems to be marginally quicker than quicksort
	//qsort_view_triangle(point);	//seems to be slower

	
	min_detail_level = 1;

	drawnQuads = 0;
	for (detail=detail_levels; detail>=min_detail_level; detail=detail/2) {
		
		if ((point[1].z - point[0].z) != 0) 
			leftm = (point[1].x-point[0].x) / ((float) point[1].z- point[0].z);
		else leftm = 0;
		if ((point[2].z - point[0].z) != 0) 
			rightm = (point[2].x-point[0].x) / ((float) point[2].z- point[0].z);
		else rightm = 0;
		leftx =(float) point[0].x;
		rightx=(float) point[0].x;	
		
		
		if ((point[1].z - point[0].z) != 0) 
			terCalc_view_triangle(point[0].z,point[1].z,
								leftx,rightx,leftm,rightm,view_angle,
								pov,detail,min_detail_level);
		

		rightx+=rightm;
		if ((point[2].z - point[1].z) != 0) 
			leftm = (point[2].x-point[1].x) / ((float) point[2].z- point[1].z);
		
		leftx  =(float) point[1].x; 
		if ((point[1].z - point[0].z) == 0) rightx =(float) point[0].x;
		
		
		terCalc_view_triangle(point[1].z,point[2].z,
								leftx,rightx,leftm,rightm,view_angle,
								pov,detail,min_detail_level);
	
	}

	glEnd();				//finish drawing quads

	//clear the dynamic terrain variables
	for (i=0;i<terrain_max_x;i++) {
		for (j=0;j<terrain_max_z;j++) {
			terrain_map(i,j).dist= -1.0;
			terrain_map(i,j).plotted=false;
			terrain_map(i,j).alt_y=(short) small_number;
		}
	}
}

void terQsort_view_triangle(vector point[]) {
	//sort view triangle using quicksort...seems 
	//slightly slower than using the sort_view_triangle() fucntion
	qsort(point, 3, sizeof(point[0]),terQsort_vt_compare);

}

int terQsort_vt_compare(const void *point_1_ptr, const void* point_2_ptr) {
//the quicksort view triangle comparison function

	vector point_1 = * (vector *) point_1_ptr;
	vector point_2 = * (vector *) point_2_ptr;

	if (point_1.z==point_2.z) return 0;
	else {
		if (point_1.z<point_2.z) return 1;
		else return -1;
	}

}

//sort the view triangles coords by y value so that it can be scan converted
void terSort_view_triangle(vector point[]) {
	//seems a little faster than quicksort..but untidy
	int j;
	vector sorted[3];

	if (point[0].z>point[1].z) 
	{
		if (point[0].z>point[2].z) 
		{
			sorted[0].x=point[0].x;
			sorted[0].z=point[0].z;

			if (point[1].z>point[2].z) 
			{
				sorted[1].x=point[1].x;
				sorted[1].z=point[1].z;

				sorted[2].x=point[2].x;
				sorted[2].z=point[2].z;
			}
			else {
				sorted[1].x=point[2].x;
				sorted[1].z=point[2].z;

				sorted[2].x=point[1].x;
				sorted[2].z=point[1].z;
			}
		}
		else
		{
			sorted[0].x=point[2].x;
			sorted[0].z=point[2].z;

			sorted[1].x=point[0].x;
			sorted[1].z=point[0].z;

			sorted[2].x=point[1].x;
			sorted[2].z=point[1].z;
		}

	}
	else
	{
		if (point[1].z>point[2].z) {
			sorted[0].x=point[1].x;
			sorted[0].z=point[1].z;
			if (point[0].z>point[2].z) 
			{
				sorted[1].x=point[0].x;
				sorted[1].z=point[0].z;

				sorted[2].x=point[2].x;
				sorted[2].z=point[2].z;
			}
			else {
				sorted[1].x=point[2].x;
				sorted[1].z=point[2].z;				

				sorted[2].x=point[0].x;
				sorted[2].z=point[0].z;
			}
		}
		else
		{
			sorted[0].x=point[2].x;
			sorted[0].z=point[2].z;

			sorted[1].x=point[1].x;
			sorted[1].z=point[1].z;

			sorted[2].x=point[0].x;
			sorted[2].z=point[0].z;
		}
	}
	for (j=0;j<3;j++) point[j].z=sorted[j].z;
	for (j=0;j<3;j++) point[j].x=sorted[j].x;
}

void terCalcVertexDistance(int x, int z, point_of_view &pov)
{
	if (terrain_map(x,z).dist == -1.0)
		terrain_map(x,z).dist
			=	sqrt(	sqr(x - pov.x)+
						sqr(z - pov.z)+
						sqr(terrain_map(x,z).y*y_scale_const - pov.y));
	//printf("new dist %lf\n", terrain_map(x,z).dist);
}

//plot the view triangle
void terCalc_view_triangle(int topz,	int botz,
						float leftx,float &rightx,
						float leftm,float &rightm,
						float view_angle,point_of_view &pov,
						int detail,short min_detail_level) {
	
	int inc,i,x,z ;
	double dist;
	
	//begin scan conversion	
	for (z= topz ; z>= botz ; z--) {    
		if (leftx<rightx) inc=1;
		else inc=-1;
		for (i=(int) leftx*inc;i<=rightx*inc;i++) {
			x=i*inc;
			//printf("5\n");
			if ((x>0)&&(x<terrain_max_x-detail-1)&&(z>0)&&(z<terrain_max_z-detail-1)) {
				//printf("1\n");
				//calc distance for vertex from view position if not already done
				terCalcVertexDistance(x,z, pov);
				terCalcVertexDistance(x+detail,z, pov);
				terCalcVertexDistance(x,z+detail, pov);
				terCalcVertexDistance(x+detail,z+detail, pov);				

				
				//if vertex lies on detail level mesh and all 4 vertexes are greater than the near detail level boundary
				if (	(x%detail==0)&&(z%detail==0) &&
						(terrain_map(x,z).dist>(detail/min_detail_level/2)*lod_dist) &&
						(terrain_map(x+detail,z).dist>(detail/min_detail_level/2)*lod_dist) &&
						(terrain_map(x,z+detail).dist>(detail/min_detail_level/2)*lod_dist) &&
						(terrain_map(x+detail,z+detail).dist>(detail/min_detail_level/2)*lod_dist) ){

					//printf("2\n");
					//if all 4 vert's are within before far detail level boundary (+a little more)
					if (	(terrain_map(x,z).dist<detail/min_detail_level*lod_dist+3.0*detail)&&
							(terrain_map(x+detail,z).dist<detail/min_detail_level*lod_dist+3.0*detail) &&
							(terrain_map(x,z+detail).dist<detail/min_detail_level*lod_dist+3.0*detail) &&
							(terrain_map(x+detail,z+detail).dist<detail/min_detail_level*lod_dist+3.0*detail)) {	
						//printf("3\n");
						//if this quad hasn't already been plotted
						if (!terrain_map(x,z).plotted) {
							//printf("4\n");
							//plot this quad
							terCreate_terrain_quad(x,z,detail);

							//set the covered quads to be "plotted" in the terrain
							terrain_map(x,z).plotted=TRUE;
							terrain_map(x+(detail/2),z).plotted=TRUE;
							terrain_map(x+(detail/2),z+(detail/2)).plotted=TRUE;
							terrain_map(x,z+(detail/2)).plotted=TRUE;
							
							
							
							if (detail>1) {
								//set up the alt_y values
								terrain_map(x+(detail/2),z).alt_y=(terrain_map(x,z).y+terrain_map(x+detail,z).y)/2+1;
								terrain_map(x+(detail),z+(detail/2)).alt_y=(terrain_map(x+detail,z).y+terrain_map(x+detail,z+detail).y)/2+1;
								terrain_map(x+(detail/2),z+detail).alt_y=(terrain_map(x,z+detail).y+terrain_map(x+detail,z+detail).y)/2+1;
								terrain_map(x,z+(detail/2)).alt_y=(terrain_map(x,z).y+terrain_map(x,z+detail).y)/2+1;
							}
						}
					}					
				}			
			}
			else {
				//vertex is off not within the map data

				//calculate the vertexes dist from viewer
				dist	=	sqrt(	sqr(x - pov.x)+
									sqr(z - pov.z)+
									sqr(pov.y));
			
				//if vertex is on detail levels mesh and within detail levels boundary
				if (	(x%detail*detail==0)&&(z%detail*detail==0) &&
					(dist>(detail/min_detail_level/2)*lod_dist)&&
					(dist<detail/min_detail_level*lod_dist+2.83*detail)) {	
					
					//set the quad colour to be the map default and add some fog
					glColor3f(	terAdd_fog(default_map_intensity*colr_ref[default_map_y].r, backgr.r, dist), 
								terAdd_fog(default_map_intensity*colr_ref[default_map_y].g, backgr.g, dist), 
								terAdd_fog(default_map_intensity*colr_ref[default_map_y].b, backgr.b, dist));
					
					//plot the quad
					if (wireframe)
					{
						glVertex3f(x*map_expansion_const ,default_map_y, z*map_expansion_const);
						glVertex3f(x*map_expansion_const ,default_map_y, (z+detail)*map_expansion_const);
						glVertex3f(x*map_expansion_const ,default_map_y, (z+detail)*map_expansion_const);
						glVertex3f((x+detail)*map_expansion_const , default_map_y, (z+detail)*map_expansion_const);
						glVertex3f((x+detail)*map_expansion_const , default_map_y, (z+detail)*map_expansion_const);
						glVertex3f((x+detail)*map_expansion_const , default_map_y, z*map_expansion_const);
						glVertex3f((x+detail)*map_expansion_const , default_map_y, z*map_expansion_const);
						glVertex3f(x*map_expansion_const ,default_map_y, z*map_expansion_const);
					}
					else
					{
						glVertex3f(x*map_expansion_const ,default_map_y, z*map_expansion_const);
						glVertex3f(x*map_expansion_const ,default_map_y, (z+detail)*map_expansion_const);
						glVertex3f((x+detail)*map_expansion_const , default_map_y, (z+detail)*map_expansion_const);
						glVertex3f((x+detail)*map_expansion_const , default_map_y, z*map_expansion_const);
					}
					
				}

			}
		}
		leftx  -=leftm;			
		rightx -=rightm;			
	}
}

float terAdd_fog(float col,float backg_col,double dist) {
//This is redundant..use opengl's hardware fog instead

/*	float fog_const=30.0f;
	float temp_const;

	if (fog_dist<55) fog_dist=55;

	if (dist<fog_dist) {
		if (dist>(fog_dist-fog_const)) {
			dist-=(fog_dist-fog_const);
			fog_const=(float) dist/fog_const;
			
			if (col<backg_col) {
				temp_const=fog_const*(backg_col-col);
				if (backg_col-col>temp_const) col+=temp_const;
				else col=backg_col;
			}
			else {
				temp_const=fog_const*(col-backg_col);
				if (col-backg_col>temp_const) col-=temp_const;
				else col=backg_col;
			}
		}
	}
	else return backg_col;
*/
	return col;
}

inline void terDraw_Vertex(int x, int z)
{

	//set the colour. add fog (the fog depends on that quads distance from the viewer)
	glColor3f(	terAdd_fog(terrain_map(x,z).col.r, backgr.r, terrain_map(x , z ).dist), 
		terAdd_fog(terrain_map(x,z).col.g, backgr.g, terrain_map(x , z ).dist), 
		terAdd_fog(terrain_map(x,z).col.b, backgr.b, terrain_map(x , z ).dist));

	//check if and alternate y value has been set, if so use that one. The alt_y is needed so that variable details works properly
	if (terrain_map(x,z).alt_y==small_number) 
	{		
		glVertex3f(x*map_expansion_const ,terrain_map(x,z).y*y_scale_const, z*map_expansion_const);				
	}
	else 
	{
		glVertex3f(x*map_expansion_const ,terrain_map(x,z).alt_y*y_scale_const, z*map_expansion_const);	
		//printf("using alt y\n");
	}
	/*if (terrain_map(x,z).alt_y != terrain_map(x,z).y)
	{

	}*/
}

//create a terrain quad at (x,z) and with side length of <detail> vertexes
void terCreate_terrain_quad(int x,int z,int detail) {
	drawnQuads++;

	if (wireframe)
	{
		terDraw_Vertex(x,z);
		terDraw_Vertex(x,z+detail);
		terDraw_Vertex(x,z+detail);
		terDraw_Vertex(x+detail,z+detail);
		terDraw_Vertex(x+detail,z+detail);
		terDraw_Vertex(x+detail,z);
		terDraw_Vertex(x+detail,z);
		terDraw_Vertex(x,z);
	}
	else
	{
		terDraw_Vertex(x,z);
		terDraw_Vertex(x,z+detail);
		terDraw_Vertex(x+detail,z+detail);
		terDraw_Vertex(x+detail,z);
	}
}

void terDeleteAll() {
	delete [] terrain;	
}
package source

import "github.com/habipokc/hezarfen/ingest/internal/geo"

// FallbackAirports lets synthetic mode run before `make seed` has filled the airports
// table: the region's large and medium airports, coordinates from OurAirports.
var FallbackAirports = []Airport{
	{Ident: "LTFM", Point: geo.Point{Lon: 28.7321, Lat: 41.2749}}, // Istanbul
	{Ident: "LTFJ", Point: geo.Point{Lon: 29.3092, Lat: 40.8986}}, // Sabiha Gökçen
	{Ident: "LTBA", Point: geo.Point{Lon: 28.8237, Lat: 40.9719}}, // Atatürk
	{Ident: "LTBU", Point: geo.Point{Lon: 27.9191, Lat: 41.1382}}, // Tekirdağ Çorlu
	{Ident: "LTBR", Point: geo.Point{Lon: 29.5626, Lat: 40.2552}}, // Bursa Yenişehir
	{Ident: "LTBH", Point: geo.Point{Lon: 26.4268, Lat: 40.1377}}, // Çanakkale
	{Ident: "LTFD", Point: geo.Point{Lon: 27.0102, Lat: 39.5525}}, // Balıkesir Koca Seyit
	{Ident: "LTBQ", Point: geo.Point{Lon: 30.0833, Lat: 40.7350}}, // Kocaeli Cengiz Topel
	{Ident: "LTBY", Point: geo.Point{Lon: 30.5193, Lat: 39.8116}}, // Eskişehir Hasan Polatkan
}

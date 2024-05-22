import pymysql
import datetime


jours = [
    (1, "Lundi", 0),
    (2, "Mardi", 1),
    (3, "Mercredi", 2),
    (4, "Jeudi", 3),
    (5, "Vendredi", 4),
    (6, "Samedi", 5),
    (7, "Dimanche", 6)
]
jour_attribution = datetime.datetime.now() + datetime.timedelta(days=2)
jour_attribution = jour_attribution.date()
jour_formattee = jour_attribution.isoformat()
indice_python = jour_attribution.weekday()
id_jour_db = next(jour[0] for jour in jours if jour[2] == indice_python)
# Fonction pour mettre à jour les taxis attribués et gérer les réservations sans taxi
def mettre_a_jour_base_de_donnees(reservations, conn):
    try:
        with conn.cursor() as cursor:
            for reservation in reservations:
                if 'idTaxi' in reservation and reservation['idTaxi'] > 0:
                    # Mise à jour de la réservation avec l'ID du taxi attribué
                    update_query = """
                    UPDATE Reservation
                    SET idTaxi = %s,
                    Etat = 3
                    WHERE idReservation = %s
                    """
                    cursor.execute(update_query, (reservation['idTaxi'], reservation['idReservation']))
                else:
                    # Mise à jour de l'état de la réservation à 4 si aucun taxi disponible
                    update_query = """
                    UPDATE Reservation
                    SET Etat = 4
                    WHERE idReservation = %s
                    """
                    cursor.execute(update_query, (reservation['idReservation'],))

            # Commit des changements
            conn.commit()

    except Exception as e:
        print(f"Une erreur s'est produite lors de la mise à jour des réservations: {e}")
        conn.rollback()
# Utilisation de la fonction pour ajuster le calcul de fin_prevue
def attribuer_taxis(taxis, reservations, jour_attribution):

    for reservation in reservations:
        taxis_compatibles = [
            t for t in taxis if (t['pecPMR'] == 'Oui' or not reservation['pecPMR'])
        ]

        taxis_disponibles = []
        for taxi in taxis_compatibles:
            chevauchement = False
            disponibilite = False  # Flag pour vérifier si le taxi est disponible

            # Convertir les heures de disponibilité en datetime
            heure_debut_matin = datetime.datetime.combine(jour_attribution, (datetime.datetime.min + taxi['HeureDebutMatin']).time())
            heure_fin_matin = datetime.datetime.combine(jour_attribution, (datetime.datetime.min + taxi['HeureFinMatin']).time())
            heure_debut_apresmidi = datetime.datetime.combine(jour_attribution, (datetime.datetime.min + taxi['HeureDebutApresMidi']).time())
            heure_fin_apresmidi = datetime.datetime.combine(jour_attribution, (datetime.datetime.min + taxi['HeureFinApresMidi']).time())

            # Heure de départ de la réservation
            heure_depart = reservation['HeureDepart']

            # Vérifier si l'heure de départ est dans une tranche horaire disponible
            if (heure_debut_matin <= heure_depart <= heure_fin_matin or
                heure_debut_apresmidi <= heure_depart <= heure_fin_apresmidi):
                disponibilite = True

            if disponibilite:
                # Supposons qu'il n'y a pas encore de taxi attribué pour simplifier
                for r in [res for res in reservations if res.get('idTaxi') == taxi['idFiche']]:
                    # Calculer la fin prévue
                    fin_prevue = r['HeureDepart'] + r['DureeTrajet'] + datetime.timedelta(hours=1)  # Ajouter la pause
                    if heure_depart < fin_prevue:
                        chevauchement = True
                        print(f"Chevauchement détecté pour taxi {taxi['idFiche']}")
                        break

            if not chevauchement and disponibilite:
                taxis_disponibles.append(taxi)

        if taxis_disponibles:
            reservation['idTaxi'] = taxis_disponibles[0]['idFiche']
            print(f"Taxi {taxis_disponibles[0]['idFiche']} attribué à la réservation.")
        else:
            print("Aucun taxi disponible pour cette réservation.")

def fetch_data(conn):
    taxi = []
    reservation = []
    with conn.cursor() as cursor:
        querytaxi = f"""SELECT USR_Fiche.idFiche, USR_Fiche.mailcontact, USR_Fiche.adresse, USR_Fiche.ville, USR_Fiche.codepostal, Vehicule.pecPMR, Disponibilite.HeureDebutMatin, Disponibilite.HeureFinMatin, Disponibilite.HeureDebutApresMidi, Disponibilite.HeureFinApresMidi
        FROM USR_Fiche 
        INNER JOIN Vehicule ON USR_Fiche.idFiche = Vehicule.idFiche 
        INNER JOIN Disponibilite ON USR_Fiche.idFiche = Disponibilite.idTaxi 
        WHERE USR_Fiche.role = 3 AND Disponibilite.idJour = {id_jour_db}"""
        cursor.execute(querytaxi)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        for row in rows:
            record = dict(zip(columns, row))
            taxi.append(record)

        queryreservation = f"SELECT * FROM Reservation WHERE Reservation.Etat = 2 AND DATE(Reservation.HeureConsult) = '{jour_formattee}'"
        cursor.execute(queryreservation)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        for row in rows:
            record = dict(zip(columns, row))
            reservation.append(record)
    return taxi, reservation
            
def main():
    # Paramètres de connexion
    hostname = '51.178.82.36'
    database = 'UperMed'
    username = 'upermed'
    password = 'hardpassword'
    port_id = 3306  # Port par défaut pour MySQL

    # Établissement de la connexion
    conn = pymysql.connect(
        host=hostname,
        user=username,
        password=password,
        database=database,
        port=port_id
    )

    try:
        
        taxi, reservation = fetch_data(conn)
        attribuer_taxis(taxi, reservation, jour_attribution)
        mettre_a_jour_base_de_donnees(reservation, conn)

    finally:
        conn.close()



if __name__ == "__main__":
    main()

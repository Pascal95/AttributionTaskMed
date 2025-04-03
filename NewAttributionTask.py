import pymysql
import datetime
import locale
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()

locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')

# Paramètres de connexion à la base de données à partir des variables d'environnement
hostname = os.getenv('DB_HOST')
database = os.getenv('DB_NAME', 'UperMed')
username = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
port_id = int(os.getenv('DB_PORT', 3306))

# Configuration des paramètres d'email à partir des variables d'environnement
smtp_user = os.getenv('SMTP_USER')
smtp_password = os.getenv('SMTP_PASSWORD')
smtp_host = os.getenv('SMTP_HOST')

jours = [
    (1, "Lundi", 0),
    (2, "Mardi", 1),
    (3, "Mercredi", 2),
    (4, "Jeudi", 3),
    (5, "Vendredi", 4),
    (6, "Samedi", 5),
    (7, "Dimanche", 6)
]
jour_attribution = datetime.datetime.now() + datetime.timedelta(days=1)
jour_attribution = jour_attribution.date()
jour_formattee = jour_attribution.isoformat()
indice_python = jour_attribution.weekday()
print(jour_attribution)
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
        
def send_email(receiver_email, nom_prenom, adresse_depart, adresse_arrivee, dateheure_consult, pec_pmr):
    sender_email = smtp_user
    password = smtp_password  # Utilisez des méthodes sécurisées pour gérer ce mot de passe
    subject = "Nouvelle course attribuée"

    # Obtenir le chemin absolu du répertoire où se trouve le script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construire le chemin absolu vers template.html
    template_path = os.path.join(script_dir, 'template.html')
    
    # Lecture du template HTML
    with open(template_path, "r") as file:
        html_template = file.read()

    # Remplacement des placeholders dans le template
    html_content = html_template.replace("[OBJET]", subject)
    html_content = html_content.replace("[NOM]", nom_prenom)
    message_details = f"""
    Une nouvelle course a été attribuée avec les détails suivants:</br>
    - Adresse de départ: {adresse_depart}</br>
    - Adresse d'arrivée: {adresse_arrivee}</br>
    - Date et heure de la course: {dateheure_consult}</br>
    - Assistance PMR nécessaire: {'Oui' if pec_pmr else 'Non'}</br>
    """
    html_content = html_content.replace("[MESSAGE]", message_details)

    # Préparation de l'e-mail
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls()
            server.login(sender_email, password)
            text = message.as_string()
            server.sendmail(sender_email, receiver_email, text)
        print("Email envoyé avec succès !")
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")


# Utilisation de la fonction pour ajuster le calcul de fin_prevue
def attribuer_taxis(taxis, reservations, jour_attribution):

    for reservation in reservations:
        if reservation['pecPMR']:
            # Filtrer les taxis compatibles avec PMR
            taxis_compatibles = [t for t in taxis if t['pecPMR'] == 'Oui']
        else:
            # Tous les taxis sont compatibles
            taxis_compatibles = taxis

        taxis_compatibles.sort(key=lambda x: (x['nombre_courses'], x['duree_totale']))
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
                    fin_prevue = r['HeureDepart'] + r['DureeTrajet'] + datetime.timedelta(minutes=30)  # Ajouter la pause
                    if heure_depart < fin_prevue:
                        chevauchement = True
                        print(f"Chevauchement détecté pour taxi {taxi['idFiche']}")
                        break

            if not chevauchement and disponibilite:
                taxis_disponibles.append(taxi)

        if taxis_disponibles:
            reservation['idTaxi'] = taxis_disponibles[0]['idFiche']
            taxis_disponibles[0]['nombre_courses'] += 1
            taxis_disponibles[0]['duree_totale'] += reservation['DureeTrajet'].total_seconds() / 3600
            nom = taxis_disponibles[0]['nom'] + " " + taxis_disponibles[0]['prenom']
            # Formater la date en français
            date_francaise = reservation['HeureConsult'].strftime('%A %d %B %Y à %H:%M')
            send_email(
                receiver_email = taxis_disponibles[0]['mailcontact'], 
                nom_prenom = nom, 
                adresse_depart = reservation['AdresseDepart'], 
                adresse_arrivee = reservation['AdresseArrive'], 
                dateheure_consult = date_francaise, 
                pec_pmr = reservation['pecPMR']
            )
            print(f"Taxi {taxis_disponibles[0]['idFiche']} attribué à la réservation.")
        else:
            print("Aucun taxi disponible pour cette réservation.")

def fetch_data(conn):
    taxi = []
    reservation = []
    with conn.cursor() as cursor:
        querytaxi = f"""SELECT USR_Fiche.idFiche,USR_Fiche.nom, USR_Fiche.prenom, USR_Fiche.mailcontact, USR_Fiche.adresse, USR_Fiche.ville, USR_Fiche.codepostal, Vehicule.pecPMR, Disponibilite.HeureDebutMatin, Disponibilite.HeureFinMatin, Disponibilite.HeureDebutApresMidi, Disponibilite.HeureFinApresMidi
        FROM USR_Fiche 
        INNER JOIN Vehicule ON USR_Fiche.idFiche = Vehicule.idFiche 
        INNER JOIN Disponibilite ON USR_Fiche.idFiche = Disponibilite.idTaxi 
        WHERE USR_Fiche.role = 3 AND Disponibilite.idJour = {id_jour_db}"""
        cursor.execute(querytaxi)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        for row in rows:
            record = dict(zip(columns, row))
            record['nombre_courses'] = 0 
            record['duree_totale'] = 0.0 
            taxi.append(record)

        queryreservation = f"SELECT * FROM Reservation WHERE Reservation.Etat = 2"
        #queryreservation = f"SELECT * FROM Reservation WHERE Reservation.Etat = 2 AND DATE(Reservation.HeureConsult) = '{jour_formattee}'"
        cursor.execute(queryreservation)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        for row in rows:
            record = dict(zip(columns, row))
            reservation.append(record)
    return taxi, reservation
            
def main():
    
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


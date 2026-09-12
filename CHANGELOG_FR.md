# Journal des modifications

*[Read in English](CHANGELOG.md)*

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format s'inspire librement de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Les versions sont suivies dans le fichier `VERSION` à la racine du dépôt.

## [0.4.7] - 2026-09-13

### Ajouté
- Pagination sur la page des transactions (50 par page, avec une
  navigation en bas du tableau), remplaçant une limite silencieuse de
  300 lignes qui masquait sinon les transactions plus anciennes sans
  aucun moyen d'y accéder.

## [0.4.6] - 2026-09-12

### Modifié
- Le solde de compte affiché sur la page des transactions correspond
  désormais au « solde net (avec report) » du mois en cours affiché sur
  la page budget mensuel, au lieu du solde complet incluant les
  transactions décalées en budget vers un mois futur.

### Ajouté
- CHANGELOG_FR.md : une traduction française maintenue de ce journal des
  modifications.

## [0.4.5] - 2026-09-12

### Corrigé
- Rapprochement bancaire : un fichier OFX téléchargé ne couvre en général
  qu'une période récente, pas tout l'historique du compte. La comparaison
  utilise désormais la période de relevé déclarée par la banque elle-même
  (ses balises `DTSTART`/`DTEND`) pour déterminer quelles opérations
  enregistrées peuvent être proposées à la suppression (« en trop »), au
  lieu de se baser sur les opérations réellement présentes dans le
  fichier — une opération hors de cette période n'est plus proposée à
  tort à la suppression.
- Le rapprochement bancaire reconnaît désormais aussi une opération
  correspondante enregistrée avec le signe inversé (recette/dépense
  inversée) au lieu de la lister à la fois comme manquante et en trop, et
  permet de la corriger avec une nouvelle action « inverser le signe » à
  côté de l'action existante de mise à jour de la date.

## [0.4.4] - 2026-09-12

### Ajouté
- Rapprochement de relevé bancaire : téléchargez un fichier OFX/QFX depuis
  la page des transactions (« 🏦 Rapprochement OFX ») pour le comparer à ce
  qui est enregistré pour le compte sélectionné. La correspondance se fait
  sur le montant exact et la date à ±7 jours près, puis vous pouvez
  corriger une date qui ne correspond pas, ajouter une opération manquante
  (en choisissant sa catégorie dans la foulée), ou supprimer une opération
  en trop — une action à la fois, en réanalysant le même fichier téléchargé
  après chaque action.

## [0.4.3] - 2026-09-12

### Ajouté
- Une deuxième case à cocher, purement visuelle, à côté de celle « revue » —
  sur la page des transactions et les deux tableaux du budget mensuel —
  celle-ci se réinitialise à chaque rechargement de page (non mémorisée),
  pour un pointage rapide en plus de celle qui est mémorisée.
- Le tableau « autres transactions du mois » de la page budget mensuel
  dispose désormais d'un bouton de modification (seul le tableau des
  récurrences validées l'avait auparavant).
- Le filtre de compte sur la page des transactions indique désormais le
  nom du propriétaire pour un compte partagé, comme les autres sélecteurs
  de compte.

## [0.4.2] - 2026-09-02

### Ajouté
- Un sous-menu « Profil » (menu utilisateur en haut à droite) pour définir
  votre fuseau horaire d'affichage. Il sert à afficher les dates/heures
  (dernière connexion, invitations...) dans votre propre heure locale, et
  — surtout — à déterminer « aujourd'hui » dans toute l'application (le
  solde réel/actuel, la mise en évidence des « transactions futures », les
  dates par défaut, les règles en retard, les périodes de rapport)
  indépendamment du fuseau horaire du serveur. Un utilisateur en avance
  sur le serveur (par ex. serveur en UTC, utilisateur en Europe/Paris)
  voit désormais son jour changer à minuit selon son propre fuseau, pas
  celui du serveur.
- L'infobulle du graphique de solde affiche désormais le montant de chaque
  opération à côté de son libellé, pas seulement le solde cumulé.
  Plusieurs transactions du même jour sont regroupées dans une seule
  infobulle au lieu de n'afficher que celle la plus proche de la souris.

## [0.4.1] - 2026-08-26

### Ajouté
- Une coche « revue » à côté du montant, sur la page des transactions et
  les tableaux de la page budget mensuel — une aide de pointage partagée
  sans aucun effet sur un solde ou un rapport. Mémorisée côté serveur,
  donc conservée entre les rechargements et visible par toute personne
  ayant accès au compte (y compris les collaborateurs d'un compte
  partagé).

### Modifié
- Sur la page budget mensuel, les tableaux des récurrences validées et
  des autres transactions trient désormais par date, la plus récente en
  premier.

### Corrigé
- Les champs montant (transactions, virements, règles récurrentes)
  tolèrent désormais ce que peut produire un relevé bancaire ou un
  clavier non anglophone — un séparateur décimal virgule, un séparateur
  de milliers espace/apostrophe/point (par ex. le suisse « 1'234.50 »),
  un symbole monétaire parasite — au lieu de planter avec une « erreur
  interne du serveur » sur tout ce qui n'était pas un simple « 1234.56 ».
  Un montant réellement invalide affiche désormais un message de
  validation clair à la place.

## [0.4.0] - 2026-08-09

### Ajouté
- Partage de compte : le propriétaire d'un compte peut le partager avec un
  autre utilisateur existant, en lecture seule ou en lecture-écriture,
  depuis la page Comptes (bouton « Partager », avec une section « Partagé
  avec moi » listant ce que d'autres vous ont partagé).
  - La lecture-écriture permet à un collaborateur d'ajouter/modifier/
    supprimer des transactions et virements sur le compte, et de gérer/
    valider ses règles récurrentes — jamais de renommer, supprimer ou
    changer le type/la devise du compte, qui restent réservés au
    propriétaire.
  - Un compte partagé se comporte comme un compte normal partout où il
    est utilisé (tableau de bord, transactions, budget mensuel, rapports),
    en utilisant les catégories du *propriétaire* pour que son budget/ses
    rapports restent cohérents, peu importe qui a réellement enregistré
    une transaction.
  - Les virements entre l'un de vos comptes et un compte partagé avec vous
    (en écriture) sont pris en charge, même entre deux propriétaires
    différents.
  - Le partage nécessite que le destinataire ait déjà un compte sur
    l'instance ; une adresse e-mail inconnue est rejetée avec un message
    d'erreur clair.
  - La révocation d'un partage prend effet immédiatement à la prochaine
    requête du collaborateur.
- Sur le tableau de bord, les comptes partagés sont visuellement
  distingués (fond bleu clair), toujours listés après vos propres
  comptes, et n'affichent le raccourci « ajouter une transaction » que si
  vous avez un accès en écriture. Le type du compte est désormais sur sa
  propre ligne sous le nom du compte.
- Le sélecteur de compte pour « ajouter une transaction » (tableau de
  bord, page transactions, budget mensuel) indique désormais le nom du
  propriétaire pour un compte partagé.

### Corrigé
- Comblé une faille latente où l'identifiant de compte envoyé dans les
  formulaires de transaction/récurrence n'était jamais vérifié par
  rapport à l'utilisateur courant avant utilisation — sans conséquence
  tant que les données étaient totalement cloisonnées, mais un réel
  risque d'écriture inter-comptes maintenant que les comptes peuvent être
  partagés.

## [0.3.5] - 2026-08-09

### Ajouté
- Sous-menu admin « Invitations » : suit chaque invitation envoyée (date
  d'envoi, expiration, si elle a été transformée en compte) et permet de
  la renvoyer, ce qui génère un nouveau lien et relance son délai
  d'expiration. Le formulaire d'invitation a été déplacé ici depuis la
  page Utilisateurs.
- La page Utilisateurs affiche désormais à la fois la « dernière
  authentification » (connexion par mot de passe) et la « dernière
  activité » (toute requête authentifiée), au lieu d'une seule colonne
  ambiguë « dernière connexion » qui ne reflétait que la première.
- Le README documente que le premier compte créé lors d'une installation
  obtient automatiquement les droits d'administrateur.
- README_FR.md : une traduction française maintenue du README.
- Une case à cocher purement visuelle à côté du montant dans les tableaux
  des récurrences validées et des autres transactions du budget mensuel,
  pour pointer manuellement pendant la relecture — aucun état sauvegardé.
- `SESSION_IDLE_TIMEOUT` : déconnecte un utilisateur après une période
  d'inactivité configurable (20 minutes par défaut, `0` pour désactiver).

### Modifié
- Les menus déroulants de la barre de navigation (Paramètres,
  Administration, menu du compte) sont désormais mutuellement exclusifs —
  en ouvrir un ferme les autres.

### Corrigé
- Les jetons CSRF n'expirent plus après l'heure par défaut de Flask-WTF
  quelle que soit la session — ils restent désormais valides pour toute
  la durée de la session, l'ancien comportement par défaut rejetant des
  soumissions légitimes (par ex. un formulaire de transaction laissé
  ouvert pendant le déjeuner). Un message convivial + une redirection
  remplacent désormais aussi la page brute « Bad Request » pour les cas
  limites restants (jeton réellement invalide).

## [0.3.4] - 2026-08-03

### Corrigé
- Le nombre de « prochaines récurrences » affiché sur le bouton budget
  mensuel du tableau de bord correspond désormais à ce que la page budget
  mensuel affiche réellement : il est limité au même compte et utilise la
  vraie date de fin de mois au lieu d'une approximation fixe au 28. Le
  nombre est désormais aussi libellé « récurrence(s) » au lieu d'afficher
  un simple chiffre.

## [0.3.3] - 2026-08-02

### Ajouté
- Rôle administrateur : le tout premier compte créé devient
  administrateur. Les administrateurs obtiennent un menu
  « Administration » (en haut à droite, à côté de Paramètres) avec une
  liste des utilisateurs affichant le rôle et la dernière connexion de
  chacun, mais pas leurs données financières.
- Les administrateurs peuvent promouvoir/rétrograder d'autres comptes en
  administrateur (au moins un administrateur doit toujours rester, et
  vous ne pouvez pas retirer vos propres droits d'administrateur),
  supprimer un compte utilisateur (efface ses données en cascade,
  impossible de se supprimer soi-même), et désactiver/réactiver un compte
  sans le supprimer — un utilisateur désactivé est immédiatement déconnecté
  et ne peut plus se reconnecter jusqu'à sa réactivation.
- Les administrateurs peuvent inviter de nouveaux utilisateurs par e-mail
  même quand l'inscription libre est désactivée, via le même mécanisme de
  lien signé expirant que la réinitialisation de mot de passe.
- Sur la page des transactions, filtrer par une catégorie parente inclut
  désormais aussi les transactions classées dans ses catégories enfants.

### Modifié
- Le menu de navigation mobile s'ouvre désormais comme un vrai panneau en
  superposition (fond de carte, ombre, cibles tactiles plus grandes) au
  lieu d'une simple pile de petits liens.

## [0.3.2] - 2026-08-01

### Ajouté
- La page des transactions affiche désormais le solde réel du compte
  sélectionné, juste sous le sélecteur de compte.

## [0.3.1] - 2026-07-31

### Corrigé
- Les fichiers statiques (JS/CSS) sont désormais servis avec
  `Cache-Control: no-cache, max-age=0`, forçant le navigateur à toujours
  revalider auprès du serveur (une requête conditionnelle peu coûteuse,
  304 si inchangé) au lieu de faire confiance à sa propre heuristique de
  durée de vie du cache. Certains navigateurs (Chrome sur Android en
  particulier) pouvaient sinon continuer à servir un script obsolète
  longtemps après un déploiement, sans autre solution que de vider
  manuellement le cache.

## [0.3.0] - 2026-07-30

### Ajouté
- Gestion des devises par utilisateur (Paramètres → Devises) : chaque
  utilisateur a sa propre liste de devises (préremplie avec EUR, CHF, USD,
  GBP — seul EUR actif par défaut), avec la possibilité
  d'activer/désactiver ou d'en ajouter de nouvelles. La création/
  modification de compte ne propose que les devises actives.
- Une devise utilisée par au moins un compte ne peut pas être désactivée
  ou supprimée — vérifié côté serveur, et les boutons correspondants sont
  entièrement masqués dans l'interface plutôt qu'affichés puis en échec.
- La migration initialise la liste de devises des utilisateurs existants
  à partir de leurs données réelles : toute devise déjà utilisée par l'un
  de leurs comptes est automatiquement activée, en plus du défaut EUR,
  pour que rien de déjà utilisé ne soit silencieusement masqué après la
  mise à jour.

## [0.2.2] - 2026-07-30

### Ajouté
- Les virements ont été fusionnés dans la page Transactions : « + Ajouter »
  se divise en « Ajouter une transaction » / « Ajouter un virement », les
  lignes de virement sont modifiables directement depuis le tableau. La
  page Virements autonome et son lien de navigation ont disparu.
- Le compte sélectionné est désormais mémorisé pour la session et reste le
  même en naviguant entre Transactions, Budget, Rapports et les
  formulaires d'ajout/modification, au lieu de revenir au compte par
  défaut à chaque fois.
- Les pièces jointes photo sont redimensionnées et réencodées côté client
  avant l'envoi (les photos prises avec un appareil photo de téléphone
  font couramment 8-12 Mo) ; les PDF et fichiers déjà petits ne sont pas
  modifiés.

### Corrigé
- Le sélecteur de date du mois budgétaire était invisible dans les
  popups d'ajout de transaction/virement (une `<dialog>` ouverte via
  `showModal()` se trouve dans le « top layer » du navigateur, donc le
  sélecteur s'affichait derrière).
- Le graphique de solde sélectionne désormais les transactions par mois
  budgétaire, comme les cartes de résumé, au lieu de la date réelle — une
  transaction décalée en budget ne disparaît plus de l'un ou de l'autre,
  et le solde final du graphique se réconcilie exactement avec le
  « solde net (avec report) » plus la prévision restante.
- « Reste à vivre (prévision) » ne fait plus double emploi avec « Solde
  net » ; son texte d'aide précise désormais explicitement qu'il exclut le
  report du mois précédent (la valeur que le point final du graphique de
  solde inclut, lui).

### Modifié
- Les cartes de résumé du budget mensuel ont été simplifiées : recettes/
  dépenses/net fusionnées en une seule carte compacte façon reçu au lieu
  de trois cartes séparées.

## [0.2.0] - 2026-07-26

Première version suivie. Gestionnaire de finances personnelles auto-hébergé
et multi-utilisateur, construit avec Flask :

- Comptes multi-devises, catégories/sous-catégories, transactions et
  virements inter-comptes (y compris multi-devises, avec montants envoyé/
  reçu séparés).
- Dépenses/recettes récurrentes avec validation mensuelle ajustable, y
  compris les virements récurrents.
- Un concept de mois budgétaire découplé de la date réelle de la
  transaction, pour qu'une opération proche d'une limite de mois puisse
  être attribuée au mois voulu.
- Vue budget mensuel avec un graphique de projection du solde jour par
  jour, et des rapports par période/mois par mois/année par année.
- Réinitialisation du mot de passe par e-mail (SMTP configurable via des
  variables d'environnement), inscription libre-service (peut être
  désactivée).
- Interface français/anglais.
- Tableaux adaptés au mobile (mise en page en cartes empilées), recherche
  instantanée côté client dans les tableaux, popup d'aperçu de pièce
  jointe intégré.
- Déploiement Docker (SQLite ou MariaDB) et Python simple, avec
  sauvegardes SQLite automatiques avant migration.

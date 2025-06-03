document.addEventListener('DOMContentLoaded', function() {
    // Pridobi reference do elementov
    const uploadForm = document.getElementById('uploadForm');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadStatus = document.getElementById('uploadStatus');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const showDbSettings = document.getElementById('showDbSettings');
    const dbSettings = document.getElementById('dbSettings');
    const checkStatusBtn = document.getElementById('checkStatusBtn');
    const dbStatus = document.getElementById('dbStatus');
    const dbStatusContent = document.getElementById('dbStatusContent');

    // Prikaži/skrij nastavitve baze podatkov
    if (showDbSettings) {
        showDbSettings.addEventListener('change', function() {
            if (this.checked) {
                dbSettings.classList.remove('d-none');
            } else {
                dbSettings.classList.add('d-none');
            }
        });
    }

    // Preveri status baze podatkov
    if (checkStatusBtn) {
        checkStatusBtn.addEventListener('click', function() {
            checkDbStatus();
        });
    }

    // Pošlji obrazec za nalaganje datoteke
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            uploadFile();
        });
    }

    // Funkcija za nalaganje datoteke
    function uploadFile() {
        const fileInput = document.getElementById('file');
        const file = fileInput.files[0];
        
        if (!file) {
            showAlert('Prosim, izberite datoteko za nalaganje.', 'warning');
            return;
        }
        
        // Preveri, ali je datoteka ustreznega tipa
        const allowedExtensions = ['.zip', '.csv'];
        const fileName = file.name.toLowerCase();
        const fileExt = fileName.substring(fileName.lastIndexOf('.'));
        
        if (!allowedExtensions.includes(fileExt)) {
            showAlert('Dovoljene so samo datoteke s končnicami: ' + allowedExtensions.join(', '), 'warning');
            return;
        }
        
        // Ustvari FormData objekt za pošiljanje
        const formData = new FormData(uploadForm);
        
        // Onemogoči gumb med nalaganjem
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Nalaganje...';
        
        // Prikaži napredek
        showProgress();
        
        // Pošlji zahtevo
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/upload', true);
        
        // Nastavi dogodke za nalaganje
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.setAttribute('aria-valuenow', percentComplete);
                progressBar.innerHTML = percentComplete + '%';
            }
        };
        
        xhr.onload = function() {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = 'Naloži in uvozi';
            
            try {
                const response = JSON.parse(xhr.responseText);
                
                // Pri uspešnem odgovoru je odgovor lahko različne oblike
                if (xhr.status === 200) {
                    if (response.message) {
                        // Nov format odgovora
                        showAlert(response.message, 'success');
                    } else if (response.success) {
                        // Star format odgovora
                        showAlert(response.message, 'success');
                    } else if (response.filename) {
                        // Še en možen format odgovora
                        showAlert('Datoteka ' + response.filename + ' uspešno naložena. ' + 
                                 (response.message || 'Uvoz podatkov se izvaja v ozadju.'), 'success');
                    } else {
                        // Nepoznan format uspešnega odgovora
                        showAlert('Datoteka uspešno naložena. Uvoz se izvaja v ozadju.', 'success');
                    }
                    
                    // Ponastavi obrazec
                    uploadForm.reset();
                    dbSettings.classList.add('d-none');
                } else {
                    // Če API vrne napako s statusom
                    let errorMsg = 'Napaka pri nalaganju: ';
                    
                    if (response.message) {
                        errorMsg += response.message;
                    } else if (response.error) {
                        errorMsg += response.error;
                    } else {
                        errorMsg += 'Neznana napaka';
                    }
                    
                    showAlert(errorMsg, 'danger');
                }
            } catch (e) {
                // Če odgovor ni veljaven JSON
                showAlert('Napaka pri obdelavi odgovora strežnika: ' + e.message, 'danger');
                console.error('Napaka pri razčlenjevanju JSON:', e);
                console.log('Odgovor strežnika:', xhr.responseText);
            }
            
            // Skrij napredek po 3 sekundah
            setTimeout(function() {
                progressContainer.classList.add('d-none');
            }, 3000);
        };
        
        xhr.onerror = function() {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = 'Naloži in uvozi';
            showAlert('Napaka pri nalaganju datoteke. Preverite povezavo.', 'danger');
            progressContainer.classList.add('d-none');
        };
        
        xhr.send(formData);
    }

    // Funkcija za prikaz opozorila
    function showAlert(message, type) {
        uploadStatus.innerHTML = message;
        uploadStatus.className = 'alert alert-' + type;
        uploadStatus.classList.remove('d-none');
        
        // Premakni se na opozorilo
        uploadStatus.scrollIntoView({ behavior: 'smooth' });
    }

    // Funkcija za prikaz napredka
    function showProgress() {
        progressContainer.classList.remove('d-none');
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        progressBar.innerHTML = '0%';
    }

    // Funkcija za preverjanje statusa baze
    function checkDbStatus() {
        checkStatusBtn.disabled = true;
        checkStatusBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Preverjanje...';
        
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                checkStatusBtn.disabled = false;
                checkStatusBtn.innerHTML = 'Preveri status baze';
                
                if (data.status === 'ok') {
                    let html = '<h5>Baza: ' + data.database + '</h5>';
                    html += '<p>Število tabel: ' + data.tables + '</p>';
                    
                    if (data.table_counts && Object.keys(data.table_counts).length > 0) {
                        html += '<table class="table table-hover table-sm">';
                        html += '<thead><tr><th>Tabela</th><th>Število zapisov</th></tr></thead>';
                        html += '<tbody>';
                        
                        for (const table in data.table_counts) {
                            html += '<tr>';
                            html += '<td>' + table + '</td>';
                            html += '<td>' + data.table_counts[table] + '</td>';
                            html += '</tr>';
                        }
                        
                        html += '</tbody></table>';
                    } else {
                        html += '<p>Ni podatkov v bazi.</p>';
                    }
                    
                    dbStatusContent.innerHTML = html;
                    dbStatus.classList.remove('d-none');
                    dbStatus.scrollIntoView({ behavior: 'smooth' });
                } else {
                    dbStatusContent.innerHTML = '<div class="alert alert-danger">' + data.message + '</div>';
                    dbStatus.classList.remove('d-none');
                }
            })
            .catch(error => {
                checkStatusBtn.disabled = false;
                checkStatusBtn.innerHTML = 'Preveri status baze';
                dbStatusContent.innerHTML = '<div class="alert alert-danger">Napaka pri preverjanju statusa: ' + error + '</div>';
                dbStatus.classList.remove('d-none');
            });
    }
}); 
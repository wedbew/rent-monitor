// Local interaction prototype. Never transmit, log or persist credentials.
const email=document.querySelector('#email');
const password=document.querySelector('#password');
const status=document.querySelector('#login-status');
const error=document.querySelector('#login-error');
let signup=false;
document.querySelector('#show-password').addEventListener('click',event=>{const shown=password.type==='password';password.type=shown?'text':'password';event.currentTarget.textContent=shown?'Ukryj':'Pokaż';event.currentTarget.setAttribute('aria-label',shown?'Ukryj hasło':'Pokaż hasło');event.currentTarget.setAttribute('aria-pressed',String(shown));});
function clearError(){error.hidden=true;email.removeAttribute('aria-invalid');password.removeAttribute('aria-invalid');}
email.addEventListener('input',clearError);password.addEventListener('input',clearError);
document.querySelector('#login-form').addEventListener('submit',event=>{
 event.preventDefault();clearError();
 if(!email.value.trim()||!email.validity.valid){error.textContent='Podaj poprawny adres e-mail.';error.hidden=false;email.setAttribute('aria-invalid','true');email.focus();return;}
 if(!password.value||(signup&&password.value.length<8)){error.textContent=signup?'Użyj hasła o długości co najmniej 8 znaków.':'Wpisz hasło, aby przejść dalej.';error.hidden=false;password.setAttribute('aria-invalid','true');password.focus();return;}
 password.value='';status.textContent=signup?'Podgląd rejestracji. Konto nie zostało utworzone. Możesz otworzyć przykładowy pulpit poniżej.':'Podgląd logowania. Dane nie zostały wysłane. Możesz otworzyć przykładowy pulpit poniżej.';
 const link=document.createElement('a');link.href='main-view.html';link.textContent='Otwórz przykładowy pulpit ↗';status.append(document.createElement('br'),link);
});
document.querySelector('#google').addEventListener('click',()=>{status.textContent='W aplikacji ten przycisk rozpocznie logowanie przez Google. W podglądzie nie łączymy się z kontem Google.';});
document.querySelector('#signup').addEventListener('click',event=>{
 signup=!signup;clearError();password.value='';password.autocomplete=signup?'new-password':'current-password';
 document.querySelector('#login-title').innerHTML=signup?'Twój nowy <span>punkt widzenia.</span>':'Witaj <span>ponownie.</span>';
 document.querySelector('#login-intro').textContent=signup?'Zacznij od jednego mieszkania. Hasło: minimum 8 znaków.':'Wróć do mieszkań, które masz na oku.';
 document.querySelector('.login-submit').innerHTML=signup?'Podgląd rejestracji <span aria-hidden="true">→</span>':'Zaloguj się <span aria-hidden="true">→</span>';
 event.currentTarget.textContent=signup?'Wróć do logowania →':'Załóż konto →';
 document.querySelector('.signup-line').firstChild.textContent=signup?'Masz już konto? ':'Pierwszy raz tutaj? ';
 document.querySelector('#forgot').hidden=signup;email.focus();
});
const recovery=document.querySelector('#recovery-dialog');
document.querySelector('#forgot').addEventListener('click',()=>{document.querySelector('#recovery-email').value=email.value;document.querySelector('#recovery-status').textContent='Podgląd — wiadomość nie zostanie wysłana.';recovery.showModal();});
document.querySelector('#close-recovery').addEventListener('click',()=>recovery.close());
recovery.addEventListener('close',()=>document.querySelector('#forgot').focus());
document.querySelector('#recovery-form').addEventListener('submit',event=>{event.preventDefault();document.querySelector('#recovery-status').textContent='Tak wyglądałby następny krok: jeśli konto istnieje, otrzymasz instrukcję na podany adres. W tym podglądzie nie wysłaliśmy wiadomości.';});

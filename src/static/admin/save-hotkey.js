// Hotkey Ctrl-S for Save button
document.addEventListener("DOMContentLoaded", function(){
  django.jQuery(()=>{
    const saveBtns = document.querySelectorAll('[name="_continue"]');
    for (const btn of saveBtns){
      btn.title = 'Press Ctrl-S';
      btn.value = `(Ctrl-S) ${btn.value}`;
    }

    // https://stackoverflow.com/a/14180949
    django.jQuery(window).bind('keydown', function(event) {
      if (event.ctrlKey || event.metaKey) {
        switch (String.fromCharCode(event.which).toLowerCase()) {
        case 's':
          event.preventDefault();
          event.preventDefault();
          document.querySelector('[name="_continue"]').click();
          return false;
        }
      }
    });
  });
});

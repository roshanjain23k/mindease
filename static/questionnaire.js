document.addEventListener("DOMContentLoaded", function(){
  const submitBtn = document.getElementById("submitQ");
  submitBtn.addEventListener("click", async function(){
    function getValues(prefix, count){
      const arr=[];
      for(let i=1;i<=count;i++){
        const els = document.getElementsByName(prefix + i);
        let val = 1;
        for(const e of els){
          if(e.checked){ val = Number(e.value); break; }
        }
        arr.push(val);
      }
      return arr;
    }
    const stress = getValues('stress_q',4);
    const anxiety = getValues('anx_q',4);
    const depression = getValues('dep_q',4);
    const social = getValues('soc_q',4);
    const parental_relation = [document.querySelector('input[name="soc_q1"]:checked').value];

    const payload = {
      user_id: localStorage.getItem('user_id') || 1,
      stress, anxiety, depression, social, parental_relation
    };

    try{
      const res = await fetch('/api/questionnaire', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
      });
      const data = await res.json();
      if(data.ok){
        // show brief modal with suggestions then go back
        let msg = `Stress: ${data.stress_score.toFixed(1)}\nAnxiety: ${data.anxiety_score.toFixed(1)}\nDepression: ${data.depression_score.toFixed(1)}\n\nSuggestions:\n`;
        if(Array.isArray(data.suggestions)){
          data.suggestions.forEach((s, idx)=>{ msg += (idx+1)+'. '+s+'\n'; });
        }
        alert(msg);

        // --- NEW: tell dashboard to refresh graphs when it opens ---
        localStorage.setItem("refreshGraphs", "true");

        window.location.href = 'dashboard.html';
      } else {
        alert('Saved');
        window.location.href = 'dashboard.html';
      }
    }catch(e){
      console.error(e);
      alert('Could not save responses.');
    }
  });
});

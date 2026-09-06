(() => {
  const input=document.getElementById('archive-search'), month=document.getElementById('archive-month');
  const rows=[...document.querySelectorAll('.archive-row')];
  function filter(){
    const query=input.value.normalize('NFKC').toLowerCase().trim();let count=0;
    rows.forEach(row=>{row.hidden=!(row.textContent.normalize('NFKC').toLowerCase().includes(query)&&(!month.value||row.dataset.date.startsWith(month.value)));if(!row.hidden)count++;});
    document.getElementById('archive-count').textContent=`显示 ${count} / ${rows.length} 期`;
    document.getElementById('archive-empty').hidden=count>0;
  }
  input.addEventListener('input',filter);month.addEventListener('change',filter);
  document.getElementById('archive-reset').addEventListener('click',()=>{input.value='';month.value='';filter();});
})();

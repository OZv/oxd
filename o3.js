o0e=1;
function xh5(c,d){
var n=c.parentNode.nextSibling;
if(d)n=n.childNodes[0];
with(n.style)
if(display!="block")display="block";
else display="none";
}
function atv(c,d,f){
c.removeAttribute("onclick");
with(c.style){
cursor="default";
outline="1px dotted gray";
}
var u="http://www.oxforddictionaries.com/media/";
if(d==1)u+="american_english/us_pron/";
else u+="english/uk_pron/";
u+=f+".mp3";
var b=function(){with(c.style){outline="";cursor="pointer";}c.setAttribute("onclick","atv(this,"+d+",'"+f+"')");};
var t=setTimeout(b,2000);
try{
with(document.createElement("audio")){
setAttribute("src",u);
onloadstart=function(){clearTimeout(t);};
onended=b;
play();
}
}catch(e){
c.style.outline="";
}
}

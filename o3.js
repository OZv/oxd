var o0e=(function(){return{
e:function(c,d){
var n=d==2?c.nextSibling:c.parentNode.nextSibling;
if(!d)n=n.childNodes[0];
with(n.style)
if(display!="block")display="block";
else display="none";
},
a:function(c,d,f){
c.removeAttribute("onclick");
with(c.style){
cursor="default";
outline="1px dotted gray";
}
var r=["english/uk_pron/","english/us_pron/","american_english/us_pron/"];
var u="http://www.oxforddictionaries.com/media/"+r[d]+f+".mp3";
var b=function(){with(c.style){outline="";cursor="pointer";}c.setAttribute("onclick","o0e.a(this,"+d+",'"+f+"')");};
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
},
x:function(c){
var n=c.parentNode.nextSibling;
with(n.style)
if(display!="none"){
display="none";
c.className="yuq";
}else{
display="block";
c.className="aej";
}
},
p:function(c){
if(c.className=="j02")
c.className="g4p";
else c.className="j02";
}
}}());

var o0e=(function(){return{
e:function(c,d){
var n=d==2?c.nextSibling:c.parentNode.nextSibling;
if(!d)n=n.childNodes[0];
var s=n.style;
if(s.display!="block")s.display="block";
else s.display="none";
},
a:function(c,d,f){
c.removeAttribute("onclick");
var s=c.style;
s.cursor="default";
s.outline="1px dotted gray";
var r=["english/uk_pron/","english/us_pron/","american_english/us_pron/"];
var u="http://www.oxforddictionaries.com/media/"+r[d]+f+".mp3";
var b=function(){s.outline="";s.cursor="pointer";c.setAttribute("onclick","o0e.a(this,"+d+",'"+f+"')");};
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
var s=c.parentNode.nextSibling.style;
if(s.display!="none"){
s.display="none";
c.className="yuq";
}else{
s.display="block";
c.className="aej";
}
},
p:function(c){
if(c.className=="j02")
c.className="g4p";
else c.className="j02";
}
}}());
